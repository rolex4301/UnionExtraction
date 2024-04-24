import copy
from datetime import date
from typing import Tuple, Union

from .abstract.GenerationPipeLineBase import GenerationPipeLineBase


class OuterJoin(GenerationPipeLineBase):

    def __init__(self, connectionHelper, global_pk_dict, delivery, projected_attributes, q_gen):
        super().__init__(connectionHelper, "Outer Join", delivery)
        self.global_pk_dict = global_pk_dict
        self.check_nep_again = False
        self.sem_eq_queries = None
        self.sem_eq_listdict = {}
        self.importance_dict = {}
        self.projected_attributes = projected_attributes
        self.Q_E = None
        self.q_gen = q_gen

    def doExtractJob(self, query: str) -> bool:
        list_of_tables, new_join_graph = self.get_tables_list_and_new_join_graph()
        final_edge_seq = self.create_final_edge_seq(list_of_tables, new_join_graph)
        table_attr_dict = self.create_table_attrib_dict()
        self.create_importance_dict(new_join_graph, query, table_attr_dict)

        set_possible_queries = self.FormulateQueries(final_edge_seq, query)
        self.remove_semantically_nonEq_queries(new_join_graph, query, set_possible_queries)
        self.Q_E = self.sem_eq_queries[0]
        return True

    def create_final_edge_seq(self, list_of_tables, new_join_graph):
        final_edge_seq = []
        queue = []
        for tab in list_of_tables:
            edge_seq = []
            temp_njg = copy.deepcopy(new_join_graph)
            queue.append(tab)
            # table_t=tab
            while len(queue) != 0:
                remove_edge = []
                table_t = queue.pop(0)
                for edge in temp_njg:
                    if edge[0][1] == table_t and edge[1][1] != table_t:
                        remove_edge.append(edge)
                        edge_seq.append(edge)
                        queue.append(edge[1][1])
                    elif edge[0][1] != table_t and edge[1][1] == table_t:
                        remove_edge.append(list(reversed(edge)))
                        edge_seq.append(list(reversed(edge)))
                        queue.append(edge[0][1])

                for i in remove_edge:
                    try:
                        temp_njg.remove(i)
                    except:
                        temp_njg.remove(list(reversed(i)))
                self.logger.debug(temp_njg)
            final_edge_seq.append(edge_seq)
        self.logger.debug("final_edge_seq: ", final_edge_seq)
        return final_edge_seq

    def create_importance_dict(self, new_join_graph, query, table_attr_dict):
        self.importance_dict = {}
        for edge in new_join_graph:
            key = tuple(edge)
            # modify d1
            # break join condition on this edge
            attrib, table = edge[0][0], edge[0][1]
            s_val = self.get_dmin_val(attrib, table)
            break_val = self.get_different_s_val(attrib, table, s_val)
            self.logger.debug(f"{table}.{attrib} s_val {s_val}, break val {break_val}")
            self.update_with_val(attrib, table, break_val)
            res_hq = self.app.doJob(query)
            self.update_with_val(attrib, table, s_val)

            # make dict of table, attributes: projected val
            loc = {}
            for table in table_attr_dict.keys():
                loc[table_attr_dict[table]] = res_hq[0].index(table_attr_dict[table])
            self.logger.debug(loc)

            res_hq_dict = {}
            if len(res_hq) == 1:
                for k in loc.keys():
                    if k not in res_hq_dict.keys():
                        res_hq_dict[k] = [None]
                    else:
                        res_hq_dict[k].append(None)
            else:
                data = res_hq[1:]
                for l in range(len(data)):
                    for k in loc.keys():
                        if k not in res_hq_dict.keys():
                            res_hq_dict[k] = [data[l][loc[k]]]
                        else:
                            res_hq_dict[k].append(data[l][loc[k]])
            self.logger.debug(res_hq_dict)

            self.importance_dict[key] = {}
            p_att_table1 = self.make_importance_dict_entry(key, edge[0][1], res_hq_dict, table_attr_dict)
            p_att_table2 = self.make_importance_dict_entry(key, edge[1][1], res_hq_dict, table_attr_dict)
            self.logger.debug(p_att_table1, p_att_table2)

        self.logger.debug(self.importance_dict)

    def make_importance_dict_entry(self, key, table, res_hq_dict, table_attr_dict):
        p_att_table = None
        attrib = table_attr_dict[table]
        if attrib in res_hq_dict.keys():
            for i in res_hq_dict[attrib]:
                if i not in [None, 'None']:
                    p_att_table = 10
                    break
        priority = 'h' if p_att_table is not None else 'l'
        self.importance_dict[key][table] = priority
        return p_att_table

    def create_table_attrib_dict(self):
        # once dict is made compare values to null or not null
        # and prepare importance_dict
        table_attr_dict = {}
        # for each table find a projected attribute which we will check for null values
        for k in self.projected_attributes:
            tabname = self.find_tabname_for_given_attrib(k)
            if tabname not in table_attr_dict.keys():
                self.logger.debug(k, tabname)
                table_attr_dict[tabname] = k
        self.logger.debug("table_attr_dict: ", table_attr_dict)
        return table_attr_dict

    def get_tables_list_and_new_join_graph(self):
        new_join_graph = []
        list_of_tables = []
        for edge in self.global_join_graph:
            temp = []
            if len(edge) > 2:
                i = 0
                while i < (len(edge)) - 1:
                    temp = []

                    self.add_tabname_for_attrib(edge[i], list_of_tables, temp)
                    self.add_tabname_for_attrib(edge[i + 1], list_of_tables, temp)

                    i = i + 1
                    new_join_graph.append(temp)
            else:
                for vertex in edge:
                    self.add_tabname_for_attrib(vertex, list_of_tables, temp)
                new_join_graph.append(temp)
        self.logger.debug("list_of_tables: ", list_of_tables)
        self.logger.debug("new_join_graph: ", new_join_graph)
        return list_of_tables, new_join_graph

    def restore_d_min(self):
        # preparing D_1
        for tabname in self.core_relations:
            self.connectionHelper.execute_sql(['alter table ' + tabname + ' rename to ' + tabname + '_restore;',
                                               'create table ' + tabname + ' as select * from ' + tabname + '4;'])

    def backup_relations(self):
        for tabname in self.core_relations:
            self.connectionHelper.execute_sql(['alter table ' + tabname + '_restore rename to ' + tabname + '2;',
                                               'drop table ' + tabname + ';',
                                               'alter table ' + tabname + '2 rename to ' + tabname + ';'])
            # The above command will inherently check if tabname1 exists

    def restore_relations(self):
        for tabname in self.core_relations:
            self.connectionHelper.execute_sql(['drop table ' + tabname + ';',
                                               'alter table ' + tabname + '_restore rename to ' + tabname + ';'])

    def remove_semantically_nonEq_queries(self, new_join_graph, query, set_possible_queries):
        # eliminate semanticamy non-equivalent querie from set_possible_queries
        # this code needs to be finished (27 feb)
        sem_eq_queries = []

        for num in range(0, len(set_possible_queries)):
            poss_q = set_possible_queries[num]
            same = True
            for edge in new_join_graph:
                attrib, table = edge[0][0], edge[0][1]
                s_val = self.get_dmin_val(attrib, table)
                break_val = self.get_different_s_val(attrib, table, s_val)
                self.logger.debug(f"{table}.{attrib} s_val {s_val}, break val {break_val}")
                self.update_with_val(attrib, table, break_val)

                # result of hidden query
                res_HQ = self.app.doJob(query)
                # result of extracted query
                res_poss_q = self.app.doJob(poss_q)
                #  maybe needs  work
                if len(res_HQ) != len(res_poss_q):
                    pass
                else:
                    # maybe use the available result comparator techniques
                    for var in range(len(res_HQ)):
                        self.logger.debug(res_HQ[var] == res_poss_q[var])
                        if not (res_HQ[var] == res_poss_q[var]):
                            same = False

                self.update_with_val(attrib, table, s_val)

            if same:
                sem_eq_queries.append(poss_q)

        self.sem_eq_queries = sem_eq_queries
        # temp_seq = self.sem_eq_queries
        # self.nep_check(sem_eq_queries, temp_seq)
        # self.restore_relations()
        # output1 = self.finalize_output()
        # self.logger.debug(output1)

    def finalize_output(self):
        for Q_E in self.sem_eq_queries:
            nep_flag = False
            outer_join_flag = False
            r = check_nep_oj.check_nep_oj(Q_E)
            if not nep_flag and not outer_join_flag:
                output1 = Q_E
                break
        return output1

    def nep_check(self, sem_eq_queries, temp_seq):
        self.check_nep_again = self.connectionHelper.config.detect_nep
        while self.check_nep_again:
            self.check_nep_again = False
            sem_eq_queries = temp_seq
            temp_seq = []
            q = sem_eq_queries[0]
            qr = nep.nep_algorithm(self.core_relations, q)
            self.logger.debug(self.sem_eq_queries)
            if qr:
                for x in self.sem_eq_queries:
                    temp_seq.append(x)
        self.sem_eq_queries = sem_eq_queries

    def add_tabname_for_attrib(self, attrib, list_of_tables, temp):
        tabname = self.find_tabname_for_given_attrib(attrib)
        if tabname not in list_of_tables:
            list_of_tables.append(tabname)
        self.logger.debug(attrib, tabname)
        temp.append((attrib, tabname))

    def update_attrib_to_see_impact(self, attrib: str, tabname: str) \
            -> Tuple[Union[int, float, date, str], Union[int, float, date, str]]:
        prev = self.connectionHelper.execute_sql_fetchone_0(
            self.connectionHelper.queries.select_attribs_from_relation([attrib], tabname))
        val = 'NULL'
        self.logger.debug(f"update {tabname}.{attrib} with value {val} that had previous value {prev}")
        self.update_with_val(attrib, tabname, val)
        return val, prev

    def FormulateQueries(self, final_edge_seq, query):
        filter_pred_on = []
        filter_pred_where = []
        for fp in self.global_filter_predicates:
            tab, attrib = fp[0], fp[1]
            _, prev = self.update_attrib_to_see_impact(attrib, tab)
            res_hq = self.app.doJob(query)
            if len(res_hq) == 1:
                filter_pred_where.append(fp)
            else:
                filter_pred_on.append(fp)
            self.update_with_val(attrib, tab, prev)
        self.logger.debug(filter_pred_on, filter_pred_where)

        set_possible_queries = []

        flat_list = [item for sublist in self.global_join_graph for item in sublist]
        keys_of_tables = [*set(flat_list)]

        tables_in_joins = [tab for tab in self.core_relations if
                           any(key in self.global_pk_dict[tab] for key in keys_of_tables)]
        tables_not_in_joins = [tab for tab in self.core_relations if tab not in tables_in_joins]

        self.logger.debug(tables_in_joins, tables_not_in_joins)

        importance_dict = self.importance_dict

        for seq in final_edge_seq:

            fp_on = copy.deepcopy(filter_pred_on)
            fp_where = copy.deepcopy(filter_pred_where)

            self.q_gen.from_op = ", ".join(tables_not_in_joins)

            flag_first = True
            for edge in seq:
                # steps to determine type of join for edge
                if tuple(edge) in importance_dict.keys():
                    imp_t1 = importance_dict[tuple(edge)][edge[0][1]]
                    imp_t2 = importance_dict[tuple(edge)][edge[1][1]]
                elif tuple(list(reversed(edge))) in importance_dict.keys():
                    imp_t1 = importance_dict[tuple(list(reversed(edge)))][edge[0][1]]
                    imp_t2 = importance_dict[tuple(list(reversed(edge)))][edge[1][1]]
                else:
                    self.logger.debug("error sneha!!!")

                self.logger.debug(imp_t1, imp_t2)
                join_map = {('l', 'l'): ' Inner Join ', ('l', 'h'): ' Right Outer Join ',
                            ('h', 'l'): ' Left Outer Join ', ('h', 'h'): ' Full Outer Join '}
                type_of_join = join_map.get((imp_t1, imp_t2))
                if flag_first:
                    self.q_gen.from_op += str(edge[0][1]) + type_of_join + str(edge[1][1]) + ' ON ' + str(
                        edge[0][0]) + ' = ' + str(edge[1][0])
                    flag_first = False
                    # check for filter predicates for both tables
                    # append fp to query
                    table1 = edge[0][1]
                    table2 = edge[1][1]
                    for fp in fp_on:
                        if fp[0] == table1 or fp[0] == table2:
                            elt = fp
                            if elt[2].strip() == 'range':
                                if '-' in str(elt[4]):
                                    predicate = elt[1] + " between " + str(elt[3]) + " and " + str(elt[4])
                                else:
                                    predicate = elt[1] + " between " + " '" + str(
                                        elt[3]) + "'" + " and " + " '" + str(elt[4]) + "'"
                            elif elt[2].strip() == '>=':
                                if '-' in str(elt[3]):
                                    predicate = elt[1] + " " + str(elt[2]) + " '" + str(elt[3]) + "' "
                                else:
                                    predicate = elt[1] + " " + str(elt[2]) + " " + str(elt[3])
                            elif 'equal' in elt[2] or 'like' in elt[2].lower() or '-' in str(elt[4]):
                                predicate = elt[1] + " " + str(elt[2]).replace('equal', '=') + " '" + str(
                                    elt[4]) + "'"
                            else:
                                predicate = elt[1] + ' ' + str(elt[2]) + ' ' + str(elt[4])
                            self.q_gen.from_op += " and " + predicate
                            # fp_on.remove(fp)

                else:
                    self.q_gen.from_op += ' ' + type_of_join + str(edge[1][1]) + ' ON ' + str(edge[0][0]) + ' = ' + str(
                        edge[1][0])
                    # check for filter predicates for second tables
                    # append fp to query

                    for fp in fp_on:
                        if fp[0] == edge[1][1]:
                            predicate = ''
                            elt = fp
                            if elt[2].strip() == 'range':
                                if '-' in str(elt[4]):
                                    predicate = elt[1] + " between " + str(elt[3]) + " and " + str(elt[4])
                                else:
                                    predicate = elt[1] + " between " + " '" + str(
                                        elt[3]) + "'" + " and " + " '" + str(elt[4]) + "'"
                            elif elt[2].strip() == '>=':
                                if '-' in str(elt[3]):
                                    predicate = elt[1] + " " + str(elt[2]) + " '" + str(elt[3]) + "' "
                                else:
                                    predicate = elt[1] + " " + str(elt[2]) + " " + str(elt[3])
                            elif 'equal' in elt[2] or 'like' in elt[2].lower() or '-' in str(elt[4]):
                                predicate = elt[1] + " " + str(elt[2]).replace('equal', '=') + " '" + str(
                                    elt[4]) + "'"
                            else:
                                predicate = elt[1] + ' ' + str(elt[2]) + ' ' + str(elt[4])
                            self.q_gen.from_op += " and " + predicate
                            # fp_on.remove(fp)
            # add other components of the query
            # + where clause
            # + group by, order by, limit
            self.q_gen.where_op = ''

            for elt in fp_where:
                if elt[2].strip() == 'range':
                    if '-' in str(elt[4]):
                        predicate = elt[1] + " between " + str(elt[3]) + " and " + str(elt[4])
                    else:
                        predicate = elt[1] + " between " + " '" + str(elt[3]) + "'" + " and " + " '" + str(
                            elt[4]) + "'"
                elif elt[2].strip() == '>=':
                    if '-' in str(elt[3]):
                        predicate = elt[1] + " " + str(elt[2]) + " '" + str(elt[3]) + "' "
                    else:
                        predicate = elt[1] + " " + str(elt[2]) + " " + str(elt[3])
                elif 'equal' in elt[2] or 'like' in elt[2].lower() or '-' in str(elt[4]):
                    predicate = elt[1] + " " + str(elt[2]).replace('equal', '=') + " '" + str(elt[4]) + "'"
                else:
                    predicate = elt[1] + ' ' + str(elt[2]) + ' ' + str(elt[4])
                if self.q_gen.where_op == '':
                    self.q_gen.where_op = predicate
                else:
                    self.q_gen.where_op = self.q_gen.where_op + " and " + predicate

            # assemble the rest of the query
            q_candidate = self.q_gen.assembleQuery()
            self.logger.debug("+++++++++++++++++++++")
            set_possible_queries.append(q_candidate)

        for q in set_possible_queries:
            self.logger.debug(q)

        return set_possible_queries

    def extract_params_from_args(self, args):
        return args[0]
