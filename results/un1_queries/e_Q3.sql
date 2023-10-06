Select o_orderkey as l_orderkey, Sum(l_quantity+l_extendedprice-1.0*l_extendedprice*l_discount) as revenue, o_orderdate, o_shippriority
From customer, lineitem, orders
Where c_custkey = o_custkey and o_orderkey = l_orderkey and c_mktsegment  = 'BUILDING' and l_shipdate  >= '1995-03-16' and o_orderdate  <= '1995-03-14'
Group By o_orderkey, o_orderdate, o_shippriority
Order By revenue desc, o_orderdate asc
Limit 10;