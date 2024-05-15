import ast

from ...src.core.abstract.GenerationPipeLineBase import GenerationPipeLineBase
from ...src.core.abstract.abstractConnection import AbstractConnectionHelper
from ...src.core.dataclass.generation_pipeline_package import PackageForGenPipeline
from ...src.util.utils import get_dummy_val_for, get_val_plus_delta, get_format, get_char

NON_TEXT_TYPES = ['date', 'int', 'integer', 'numeric', 'float']


def has_attrib_key_condition(attrib, attrib_inner, key_list):
    return attrib_inner == attrib or attrib_inner in key_list


class GroupBy(GenerationPipeLineBase):
    def __init__(self, connectionHelper: AbstractConnectionHelper,
                 genPipelineCtx: PackageForGenPipeline,
                 pgao_ctx):
        super().__init__(connectionHelper, "Group By", genPipelineCtx)
        self.projected_attribs = pgao_ctx.projected_attribs
        self.has_groupby = False
        self.group_by_attrib = []

    def doExtractJob(self, query):
        for i in range(len(self.core_relations)):
            tabname = self.core_relations[i]
            attrib_list = self.global_all_attribs[i]

            for attrib in attrib_list:
                self.truncate_core_relations()

                # determine offset values for this attribute
                curr_attrib_value = [0, 1, 1]

                key_list = next((elt for elt in self.global_join_graph if attrib in elt), [])

                # For this table (tabname) and this attribute (attrib), fill all tables now
                for j in range(len(self.core_relations)):
                    tabname_inner = self.core_relations[j]
                    attrib_list_inner = self.global_all_attribs[j]

                    insert_rows = []

                    no_of_rows = 3 if tabname_inner == tabname else 1
                    key_path_flag = any(val in key_list for val in attrib_list_inner)
                    if tabname_inner != tabname and key_path_flag:
                        no_of_rows = 2

                    attrib_list_str = ",".join(attrib_list_inner)
                    att_order = f"({attrib_list_str})"

                    for k in range(no_of_rows):
                        insert_values = []
                        for attrib_inner in attrib_list_inner:
                            datatype = self.get_datatype((tabname_inner, attrib_inner))

                            if has_attrib_key_condition(attrib, attrib_inner, key_list):
                                self.insert_values_for_joined_attribs(attrib_inner, curr_attrib_value, datatype,
                                                                      insert_values, k, tabname_inner)
                            else:
                                self.insert_values_for_single_attrib(attrib_inner, datatype, insert_values,
                                                                     tabname_inner)
                        insert_rows.append(tuple(insert_values))

                    self.insert_attrib_vals_into_table(att_order, attrib_list_inner, insert_rows, tabname_inner)

                self.see_d_min()
                new_result = self.app.doJob(query)

                if self.app.isQ_result_empty(new_result):
                    self.logger.error('some error in generating new database. '
                                      'Result is empty. Can not identify Grouping')
                    return False
                elif len(new_result) == 3:
                    # 3 is WITH HEADER so it is checking for two rows
                    self.group_by_attrib.append(attrib)
                    self.has_groupby = True
                elif len(new_result) == 2:
                    # It indicates groupby on at least one attribute
                    self.has_groupby = True

        self.remove_duplicates()

        for elt in self.global_filter_predicates:
            if elt[1] not in self.group_by_attrib and elt[1] in self.projected_attribs and (
                    elt[2] == '=' or elt[2] == 'equal'):
                self.group_by_attrib.append(elt[1])
        self.logger.debug(self.group_by_attrib)
        return True

    def insert_values_for_single_attrib(self, attrib_inner, datatype, insert_values, tabname_inner):
        if datatype in NON_TEXT_TYPES:
            val = self.get_insert_value_for_single_attrib(datatype, attrib_inner, tabname_inner)
            if datatype == 'date':
                insert_values.append(ast.literal_eval(get_format('date', val)))
            else:
                insert_values.append(get_format('int', val))
        else:
            if (tabname_inner, attrib_inner) in self.filter_attrib_dict.keys():
                filtered_val = self.get_s_val_for_textType(attrib_inner, tabname_inner)
                char_val = filtered_val.replace('%', '')
            else:
                char_val = get_char(get_dummy_val_for('char'))
            insert_values.append(char_val)

    def insert_values_for_joined_attribs(self, attrib_inner, curr_attrib_value, datatype, insert_values, k,
                                         tabname_inner):
        delta = curr_attrib_value[k]
        if datatype in NON_TEXT_TYPES:
            val = self.get_insert_value_for_joined_attribs(datatype, attrib_inner,
                                                           delta, tabname_inner)
            if datatype == 'date':
                insert_values.append(ast.literal_eval(get_format('date', val)))
            else:
                insert_values.append(get_format('int', val))
        else:
            plus_val = get_char(get_val_plus_delta('char', get_dummy_val_for('char'), delta))
            if (tabname_inner, attrib_inner) in self.filter_attrib_dict.keys():
                filtered_val = self.get_s_val_for_textType(attrib_inner, tabname_inner)
                if '_' in filtered_val:
                    insert_values.append(filtered_val.replace('_', plus_val))
                else:
                    insert_values.append(filtered_val.replace('%', plus_val, 1))
                insert_values[-1].replace('%', '')
            else:
                insert_values.append(plus_val)

    def get_insert_value_for_single_attrib(self, datatype, attrib_inner, tabname_inner):
        if (tabname_inner, attrib_inner) in self.filter_attrib_dict.keys():
            val = self.filter_attrib_dict[(tabname_inner, attrib_inner)][0]
        else:
            val = get_dummy_val_for(datatype)
        return val

    def get_insert_value_for_joined_attribs(self, datatype, attrib_inner, delta, tabname_inner):
        if (tabname_inner, attrib_inner) in self.filter_attrib_dict.keys():
            zero_val = get_val_plus_delta(datatype,
                                          self.filter_attrib_dict[
                                              (tabname_inner, attrib_inner)][0], delta)
            one_val = self.filter_attrib_dict[(tabname_inner, attrib_inner)][1]
            val = min(zero_val, one_val)
        else:
            val = get_val_plus_delta(datatype, get_dummy_val_for(datatype), delta)
        return val

    def remove_duplicates(self):
        to_remove = []
        for attrib in self.group_by_attrib:
            if attrib not in self.projected_attribs:
                to_remove.append(attrib)
        for r in to_remove:
            self.group_by_attrib.remove(r)
        self.group_by_attrib.sort()
