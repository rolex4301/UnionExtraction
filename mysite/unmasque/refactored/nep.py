import ast

from .abstract.GenerationPipeLineBase import GenerationPipeLineBase
from .abstract.MinimizerBase import Minimizer
from .result_comparator import ResultComparator
from .util.common_queries import get_restore_name, drop_table
from .util.utils import get_dummy_val_for, get_format, get_char


class NEP(Minimizer, GenerationPipeLineBase):

    def __init__(self, connectionHelper, core_relations, all_sizes,
                 global_pk_dict,
                 global_all_attribs,
                 global_attrib_types,
                 filter_predicates,
                 global_key_attributes,
                 query_generator):
        Minimizer.__init__(self, connectionHelper, core_relations, all_sizes, "NEP")
        GenerationPipeLineBase.__init__(self, connectionHelper, "NEP",
                                        core_relations,
                                        global_all_attribs,
                                        global_attrib_types,
                                        None,
                                        filter_predicates)
        self.Q_E = ""
        self.global_pk_dict = global_pk_dict  # from initialization
        self.global_key_attributes = global_key_attributes
        self.query_generator = query_generator
        self.result_comparator = ResultComparator(self.connectionHelper, True)

    def extract_params_from_args(self, args):
        print(args)
        return args[0], args[1]

    def doActualJob(self, args):
        query, Q_E = self.extract_params_from_args(args)
        core_sizes = self.getCoreSizes()

        # STORE STARTING POINT(OFFSET) AND NOOFROWS(LIMIT) FOR EACH TABLE IN FORMAT (offset, limit)
        partition_dict = {}
        for key in core_sizes.keys():
            partition_dict[key] = (0, core_sizes[key])

        self.create_all_views()

        # Run the hidden query on the original database instance
        matched = self.result_comparator.check_matching(query, Q_E)
        if matched:
            nep_exists = False
            self.Q_E = Q_E
            self.logger.info("NEP doesn't exists under our assumptions")
        else:
            self.logger.info("NEP may exists")
            while not matched:
                for i in range(len(self.core_relations)):
                    tabname = self.core_relations[i]
                    self.Q_E = self.nep_db_minimizer(query, tabname, Q_E, core_sizes[tabname], partition_dict[tabname],
                                                     i)
                    matched = self.result_comparator.check_matching(query, self.Q_E)
                    self.logger.debug(matched)
            nep_exists = True

        self.drop_all_views()
        return nep_exists

    def create_all_views(self):
        for tabname in self.core_relations:
            self.connectionHelper.execute_sql([drop_table(tabname),
                                               "create view " + tabname + " as select * from "
                                               + get_restore_name(tabname) + " ;"])
        self.logger.info("all views created.")

    def drop_all_views(self):
        for tabname in self.core_relations:
            self.connectionHelper.execute_sql(["alter view " + tabname + " rename to " + tabname + "3;",
                                               "create table " + tabname + " as select * from " + tabname + "3;",
                                               "drop view " + tabname + "3 CASCADE;"])
        self.logger.info("all views dropped.")

    def nep_db_minimizer(self, query, tabname, Q_E, tab_size, partition_dict, i):
        self.logger.debug("nep_db_minimizer", tabname, tab_size, partition_dict, i)
        # Run the hidden query on this updated database instance with table T_u
        matched = self.result_comparator.check_matching(query, Q_E)

        # Base Case
        if tab_size == 1 and not matched:
            val = self.extract_NEP_value(query, tabname, i)
            if val:
                self.logger.info("Extracting NEP value")
                return self.query_generator.updateExtractedQueryWithNEPVal(query, val)
            else:
                return Q_E

        # Drop the current view of name tabname
        # Make a view of name x with first half  T <- T_u
        self.connectionHelper.execute_sql(["drop view " + tabname + " CASCADE;",
                                           self.create_view_with_upper_half(partition_dict, tabname)])

        if not self.result_comparator.check_matching(query, Q_E):
            Q_E_ = self.nep_db_minimizer(query, tabname, Q_E, int(partition_dict[1] / 2),
                                         (int(partition_dict[0]), int(partition_dict[1] / 2)), i)
        else:
            Q_E_ = Q_E
        return self.get_QE_from_lower_half(Q_E_, i, partition_dict, query, tabname)

    def get_QE_from_lower_half(self, Q_E, i, partition_dict, query, tabname):
        # Drop the view of name tabname
        # Make a view of name x with second half  T <- T_l
        self.connectionHelper.execute_sql(["drop view " + tabname + " CASCADE;",
                                           self.create_view_with_lower_half(partition_dict, tabname)])
        # Run the hidden query on this updated database instance with table T_l
        if not self.result_comparator.check_matching(query, Q_E):
            Q_E_ = self.nep_db_minimizer(query, tabname, Q_E, int(partition_dict[1]) - int(partition_dict[1] / 2),
                                         (int(partition_dict[0]) + int(partition_dict[1] / 2),
                                          int(partition_dict[1]) - int(partition_dict[1] / 2)), i)
            return Q_E_
        else:
            return Q_E

    def create_view_with_lower_half(self, partition_dict, tabname):
        self.logger.info("Creating view with lower half.")
        offset = int(partition_dict[0]) + int(partition_dict[1] / 2)
        limit = int(partition_dict[1]) - int(partition_dict[1] / 2)
        return self.create_view_from_offset_limit(limit, offset, tabname)

    def create_view_from_offset_limit(self, limit, offset, tabname):
        self.logger.debug("offset ", offset, " limit ", limit)
        return "create view " + tabname + " as select * from " + get_restore_name(
            tabname) + " order by " + self.global_pk_dict[tabname] + " offset " + str(offset) \
            + " limit " + str(limit) + ";"

    def create_view_with_upper_half(self, partition_dict, tabname):
        self.logger.info("Creating view with upper half.")
        offset = int(partition_dict[0])
        limit = int(partition_dict[1] / 2)
        return self.create_view_from_offset_limit(limit, offset, tabname)

    def extract_NEP_value(self, query, tabname, i):
        # Return if hidden executable is giving non-empty output on the reduced database
        # It means that the current table doesnot contain NEP source column
        new_result = self.app.doJob(query)
        if len(new_result) > 1:
            return False

        # check nep for every non-key attribute by changing its value to different s value and run the executable.
        # If the output came out non- empty. It means that nep is present on that attribute with previous value.
        attrib_types_dict = {(entry[0], entry[1]): entry[2] for entry in self.global_attrib_types}

        filter_attrib_dict = self.construct_filter_attribs_dict()

        attrib_list = [self.global_all_attribs[i]]
        filterAttribs = []

        # convert the view into a table
        self.connectionHelper.execute_sql(["alter view " + tabname + " rename to " + tabname + "_nep ;",
                                           "create table " + tabname + " as select * from " + tabname + "_nep ;"])

        for attrib in attrib_list:
            if attrib not in self.global_key_attributes:
                if 'date' in attrib_types_dict[(tabname, attrib)]:
                    if (tabname, attrib) in filter_attrib_dict.keys():
                        val = min(filter_attrib_dict[(tabname, attrib)][0],
                                  filter_attrib_dict[(tabname, attrib)][1])
                    else:
                        val = get_dummy_val_for('date')
                    val = ast.literal_eval(get_format(val))

                elif ('int' in attrib_types_dict[(tabname, attrib)] or 'numeric' in attrib_types_dict[
                    (tabname, attrib)]):
                    # check for filter (#MORE PRECISION CAN BE ADDED FOR NUMERIC#)
                    if (tabname, attrib) in filter_attrib_dict.keys():
                        val = min(filter_attrib_dict[(tabname, attrib)][0],
                                  filter_attrib_dict[(tabname, attrib)][1])
                    else:
                        val = get_dummy_val_for('int')
                else:
                    if (tabname, attrib) in filter_attrib_dict.keys():
                        val = (filter_attrib_dict[(tabname, attrib)].replace('%', ''))
                    else:
                        val = get_char(get_dummy_val_for('char'))

                # prev = self.connectionHelper.execute_sql_fetchone_0("SELECT " + attrib + " FROM " + tabname + ";")

                if 'date' in attrib_types_dict[(tabname, attrib)]:
                    update_q = "UPDATE " + tabname + " SET " + attrib + " = " + val + ";"
                elif 'int' in attrib_types_dict[(tabname, attrib)] or 'numeric' in attrib_types_dict[(tabname, attrib)]:
                    update_q = "UPDATE " + tabname + " SET " + attrib + " = " + str(val) + ";"
                else:
                    update_q = "UPDATE " + tabname + " SET " + attrib + " = '" + val + "';"
                self.connectionHelper.execute_sql([update_q])

                new_result = self.app.doJob(query)

                if len(new_result) > 1:
                    # convert the table back to view
                    self.connectionHelper.execute_sql(["drop table " + tabname + ";",
                                                       "alter view " + tabname + "_nep rename to " + tabname + ";"])
                    return filterAttribs

        # convert the table back to view
        self.connectionHelper.execute_sql(["drop table " + tabname + ";",
                                           "alter view " + tabname + "_nep rename to " + tabname + ";"])
        return False
