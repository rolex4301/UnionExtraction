import ast
import copy

from .MutationPipeLineBase import MutationPipeLineBase
from ..util.common_queries import insert_into_tab_attribs_format, update_tab_attrib_with_value, \
    update_tab_attrib_with_quoted_value
from ...refactored.util.utils import get_escape_string, get_dummy_val_for, get_format, get_char, get_unused_dummy_val

NUMBER_TYPES = ['int', 'integer', 'numeric', 'float']


class GenerationPipeLineBase(MutationPipeLineBase):

    def __init__(self, connectionHelper, name, delivery):
        super().__init__(connectionHelper, delivery.core_relations, delivery.global_min_instance_dict, name)
        self.global_all_attribs = delivery.global_all_attribs
        self.global_attrib_types = delivery.global_attrib_types
        self.global_join_graph = delivery.global_join_graph
        self.global_filter_predicates = delivery.global_filter_predicates
        self.filter_attrib_dict = delivery.filter_attrib_dict
        self.attrib_types_dict = delivery.attrib_types_dict
        self.joined_attribs = delivery.joined_attribs

    def extract_params_from_args(self, args):
        return args[0]

    def doActualJob(self, args):
        query = self.extract_params_from_args(args)
        self.do_init()
        check = self.doExtractJob(query)
        return check

    def restore_d_min_from_dict(self):
        for tab in self.core_relations:
            values = self.global_min_instance_dict[tab]
            attribs, vals = values[0], values[1]
            for i in range(len(attribs)):
                attrib, val = attribs[i], vals[i]
                self.update_with_val(attrib, tab, val)

    def do_init(self):
        self.restore_d_min_from_dict()
        self.see_d_min()

    def get_datatype(self, tab_attrib):
        if any(x in self.attrib_types_dict[tab_attrib] for x in ['int', 'integer']):
            return 'int'
        elif 'date' in self.attrib_types_dict[tab_attrib]:
            return 'date'
        elif any(x in self.attrib_types_dict[tab_attrib] for x in ['text', 'char', 'varbit']):
            return 'str'
        elif any(x in self.attrib_types_dict[tab_attrib] for x in ['numeric', 'float']):
            return 'numeric'
        else:
            raise ValueError

    def get_s_val_for_textType(self, attrib_inner, tabname_inner):
        filtered_val = self.filter_attrib_dict[(tabname_inner, attrib_inner)]
        if isinstance(filtered_val, tuple):
            filtered_val = filtered_val[0]
        return filtered_val

    def insert_attrib_vals_into_table(self, att_order, attrib_list_inner, insert_rows, tabname_inner):
        esc_string = get_escape_string(attrib_list_inner)
        insert_query = insert_into_tab_attribs_format(att_order, esc_string, tabname_inner)
        self.connectionHelper.execute_sql_with_params(insert_query, insert_rows)

    def update_attrib_in_table(self, attrib, value, tabname):
        update_query = update_tab_attrib_with_value(attrib, tabname, value)
        self.connectionHelper.execute_sql([update_query])

    def doExtractJob(self, query):
        return True

    def get_other_attribs_in_eqJoin_grp(self, attrib):
        other_attribs = []
        for join_edge in self.global_join_graph:
            if attrib in join_edge:
                other_attribs = copy.deepcopy(join_edge)
                other_attribs.remove(attrib)
                break
        return other_attribs

    def update_attribs_bulk(self, join_tabnames, other_attribs, val):
        for other_attrib in other_attribs:
            join_tabname = self.find_tabname_for_given_attrib(other_attrib)
            join_tabnames.append(join_tabname)
            self.update_with_val(other_attrib, join_tabname, val)

    def update_attrib_to_see_impact(self, attrib, tabname):
        prev = self.connectionHelper.execute_sql_fetchone_0(f"SELECT {attrib} FROM {tabname};")
        val = self.get_different_s_val(attrib, tabname, prev)
        self.logger.debug("update ", tabname, attrib, "with value ", val, " prev", prev)
        self.update_with_val(attrib, tabname, val)
        return val, prev

    def update_with_val(self, attrib, tabname, val):
        datatype = self.get_datatype((tabname, attrib))
        if datatype == 'date' or datatype in NUMBER_TYPES:
            update_q = update_tab_attrib_with_value(attrib, tabname, get_format(datatype, val))
        else:
            update_q = update_tab_attrib_with_quoted_value(tabname, attrib, val)
        self.connectionHelper.execute_sql([update_q])

    def get_s_val(self, attrib, tabname):
        datatype = self.get_datatype((tabname, attrib))
        if datatype == 'date':
            if (tabname, attrib) in self.filter_attrib_dict.keys():
                val = min(self.filter_attrib_dict[(tabname, attrib)][0],
                          self.filter_attrib_dict[(tabname, attrib)][1])
            else:
                val = get_dummy_val_for(datatype)
            val = ast.literal_eval(get_format(datatype, val))

        elif datatype in NUMBER_TYPES:
            # check for filter (#MORE PRECISION CAN BE ADDED FOR NUMERIC#)
            if (tabname, attrib) in self.filter_attrib_dict.keys():
                val = min(self.filter_attrib_dict[(tabname, attrib)][0],
                          self.filter_attrib_dict[(tabname, attrib)][1])
            else:
                val = get_dummy_val_for(datatype)
        else:
            if (tabname, attrib) in self.filter_attrib_dict.keys():
                val = self.get_s_val_for_textType(attrib, tabname)
                self.logger.debug(val)
                val = val.replace('%', '')
            else:
                val = get_char(get_dummy_val_for('char'))
        return val

    def get_different_val_for_dmin(self, attrib, tabname, prev):
        if prev == self.filter_attrib_dict[(tabname, attrib)][0]:
            val = self.filter_attrib_dict[(tabname, attrib)][1]
        elif prev == self.filter_attrib_dict[(tabname, attrib)][1]:
            val = self.filter_attrib_dict[(tabname, attrib)][0]
        else:
            val = min(self.filter_attrib_dict[(tabname, attrib)][0],
                      self.filter_attrib_dict[(tabname, attrib)][1])
        return val

    def get_different_s_val(self, attrib, tabname, prev):
        datatype = self.get_datatype((tabname, attrib))
        if datatype == 'date':
            if (tabname, attrib) in self.filter_attrib_dict.keys():
                val = self.get_different_val_for_dmin(attrib, tabname, prev)
            else:
                val = get_unused_dummy_val(datatype, [prev])
            val = ast.literal_eval(get_format(datatype, val))

        elif datatype in NUMBER_TYPES:
            # check for filter (#MORE PRECISION CAN BE ADDED FOR NUMERIC#)
            if (tabname, attrib) in self.filter_attrib_dict.keys():
                val = self.get_different_val_for_dmin(attrib, tabname, prev)
            else:
                val = get_unused_dummy_val(datatype, [prev])
        else:
            if (tabname, attrib) in self.filter_attrib_dict.keys():
                val = self.get_s_val_for_textType(attrib, tabname)
                self.logger.debug(val)
                val = val.replace('%', '')
            else:
                val = get_char(get_unused_dummy_val('char', [prev]))
        return val

    def find_tabname_for_given_attrib(self, find_attrib):
        for entry in self.global_attrib_types:
            tabname = entry[0]
            attrib = entry[1]
            if attrib == find_attrib:
                return tabname
