import unittest

from mysite.unmasque.src.core import UnionPipeLine, algorithm1
from mysite.unmasque.src.core.union_from_clause import UnionFromClause
from mysite.unmasque.src.util.ConnectionHelper import ConnectionHelper
from mysite.unmasque.test.util import queries


class MyTestCase(unittest.TestCase):
    conn = ConnectionHelper()

    def test_nonUnion_query(self):
        key = 'tpch_query1'
        query = queries.queries_dict[key]
        u_Q, tp = UnionPipeLine.extract(self.conn, query)
        self.assertTrue(u_Q is not None)
        print(u_Q)
        tp.print()

    def test_nonUnion_query_Q2(self):
        key = 'Q3'
        query = queries.queries_dict[key]
        u_Q, tp = UnionPipeLine.extract(self.conn, query)
        self.assertTrue(u_Q is not None)
        print(u_Q)
        tp.print()

    def test_nonUnion_queries(self):
        Q_keys = queries.queries_dict.keys()
        f = open("UnionPipeLineTest_results.txt.txt", "w")
        q_no = 1
        for q_key in Q_keys:
            query = queries.queries_dict[q_key]
            u_Q, tp = UnionPipeLine.extract(self.conn, query)
            self.assertTrue(u_Q is not None)
            print(u_Q)
            f.write("\n" + str(q_no) + ":")
            f.write("\tHidden Query:\n")
            f.write(query)
            f.write("\n*** Extracted Query:\n")
            f.write(u_Q)
            f.write("\n---------------------------------------\n")
            tp.print()
            q_no += 1
        f.close()

    def test_unionQ(self):
        query = "(select l_partkey as key from lineitem, part where l_partkey = p_partkey and l_extendedprice <= 905) " \
                "union all " \
                "(select l_orderkey as key from lineitem, orders where l_orderkey = o_orderkey and o_totalprice <= " \
                "905) " \
                "union all " \
                "(select o_orderkey as key from customer, orders where c_custkey = o_custkey and o_totalprice <= 890);"
        u_Q, tp = UnionPipeLine.extract(self.conn, query)
        self.assertTrue(u_Q is not None)
        print(u_Q)
        f = open("check.txt", 'w')
        f.write(query + "\n\n")
        f.write(u_Q)
        f.close()
        tp.print()

    def test_unionQuery_ui_caught_case(self):
        self.conn.connectUsingParams()
        query = "(SELECT c_custkey as key, c_name as name FROM customer, nation where c_nationkey = n_nationkey and " \
                "n_name = 'UNITED STATES') UNION ALL " \
                "(SELECT p_partkey as key, p_name as name FROM part , lineitem where p_partkey = l_partkey " \
                "and l_quantity > 35);"

        db = UnionFromClause(self.conn)
        p, pstr = algorithm1.algo(db, query)
        self.assertEqual(p, {frozenset({'customer', 'nation'}), frozenset({'part', 'lineitem'})})
        self.assertTrue(pstr is not None)
        self.conn.closeConnection()

    def test_random_nonUnion(self):
        query = "SELECT o_orderdate, SUM(l_extendedprice) AS total_price " \
                "FROM orders, lineitem where o_orderkey = l_orderkey " \
                "and o_orderdate <= '1995-01-01' GROUP BY o_orderdate " \
                "ORDER BY total_price DESC LIMIT 10;"
        eq, _ = UnionPipeLine.extract(self.conn, query)
        print(eq)
        self.assertEqual(eq, "(Select o_orderdate, Sum(l_extendedprice) as total_price"
                             "\nFrom orders, lineitem\n"
                             "Where o_orderkey = l_orderkey and o_orderdate  <= '1995-01-02'\n"
                             "Group By o_orderdate\nOrder By total_price desc, o_orderdate desc\nLimit 10;)")

    def test_another(self):
        query = "SELECT l_orderkey as key, l_quantity as dummy, " \
                "l_partkey as s_key FROM lineitem WHERE l_shipdate >= DATE '1994-01-01'" \
                " AND l_shipdate < DATE '1995-01-01' " \
                "AND l_quantity > 30 UNION ALL SELECT " \
                "ps_partkey as key, ps_supplycost as dummy, " \
                "ps_suppkey as s_key FROM partsupp, orders WHERE" \
                " partsupp.ps_suppkey = orders.o_custkey " \
                "AND orders.o_orderdate >= DATE '1994-01-01' AND orders.o_orderdate < DATE '1995-01-01' " \
                "AND partsupp.ps_supplycost < 100;"
        eq, _ = UnionPipeLine.extract(self.conn, query)
        print(eq)


if __name__ == '__main__':
    unittest.main()