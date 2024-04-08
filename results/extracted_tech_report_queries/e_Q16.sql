Select p_brand, p_type, p_size, Count(*) as supplier_cnt
 From part, partsupp 
 Where p_partkey = ps_partkey
 and p_size  >= 4 
 Group By p_brand, p_size, p_type 
 Order By supplier_cnt desc, p_brand asc, p_type asc, p_size asc;