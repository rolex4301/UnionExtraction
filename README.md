# Text2SQL on TPCH Benchmark Queries using GPT-4o (04-04-2025):

| QID  | Business Text       | Ground Truth   | GPT Output                          | Remarks on Diff                                |
|------|---------------------|----------------|-------------------------------------|-------------------------------------------------|
| Q2 |    The Query finds, in Europe, for each part made of Brass and of size 15, the supplier who can supply it at minimum cost. If several European suppliers offer the desired part type and size at the same (minimum) cost, the query lists the parts from suppliers with the 100 highest account balances. For each supplier, the query lists the supplier’s account balance, name and nation; the part’s number and manufacturer; the supplier’s address, phone number and comment information.                                   |      select s_acctbal,s_name,n_name,p_partkey,p_mfgr,s_address,s_phone,s_comment from part,supplier,partsupp,nation,region where p_partkey = ps_partkey and s_suppkey = ps_suppkey and p_size = 15 and p_type like '%BRASS' and s_nationkey = n_nationkey and n_regionkey = r_regionkey and r_name = 'EUROPE' and ps_supplycost = (select min(ps_supplycost) from partsupp,supplier,nation,region where p_partkey = ps_partkey and s_suppkey = ps_suppkey and s_nationkey = n_nationkey and n_regionkey = r_regionkey and r_name = 'EUROPE') order by s_acctbal desc, n_name, s_name, p_partkey limit 100;                              |   https://chatgpt.com/share/67ef8147-b3d4-8005-9bcd-21444bf63e26                                  |     https://www.diffchecker.com/zWuU3Apc/                                            |
|Q16|||https://chatgpt.com/share/67ef90f2-07d8-8005-8d08-7ed6beed5a2f|projection, group by missing.|
|Q17|||https://chatgpt.com/share/67ef8e4a-a63c-8005-8d57-c719d4abbb4d|2 instances of part. Extra filters inside.|
|Q18|||https://chatgpt.com/share/67ef8c4d-1968-8005-a5ae-cfb3cb8d4b41|Missing lineitem table. Incorrect inner aggregation. Semijoin on different attribute. Group by incorrect.|
|Q20 |The query identifies suppliers who have an excess of a given part available; an excess is defined to be more than 50% of the parts like the given part that the supplier shipped in 1995 for France. Only parts made of Ivory are considered.|select s_name,s_address from supplier, nation where s_suppkey in (select ps_suppkey from partsupp where ps_partkey in ( select p_partkey from part where p_name like '%ivory%') and ps_availqty > (select 0.5 * sum(wl_quantity) from lineitem where l_partkey = ps_partkey and l_suppkey = ps_suppkey and l_shipdate >= date '1995-01-01' and l_shipdate < date '1995-01-01' + interval '1' year))and s_nationkey = n_nationkey and n_name = 'FRANCE' order by s_name|https://chatgpt.com/share/67ef644d-131c-8005-8a3d-ef14d8bb48a4|Orders table is spurious. o_orderdate is in filter instead of l_shipdate.|
|Q21|||https://chatgpt.com/share/67ef8b7d-4dec-8005-bdde-5e0573bd6e19|Missing projection and group by.|
| Q22  |  This query counts how many customers within a specific range of country codes have not placed orders for 7 years but who have a greater than average “positive” account balance. It also reflects the magnitude of that balance. Country code is defined as the first two characters of c_phone.|select cntrycode,count(*) as numcust,sum(c_acctbal) as totacctbalfrom(selectsubstring(c_phone from 1 for 2) as cntrycode,c_acctbal from customer where substring(c_phone from 1 for 2) in ('13', '31', '23', '29', '30', '18', '17') and c_acctbal > (select avg(c_acctbal) from customer where c_acctbal > 0.00 and substring(c_phone from 1 for 2) in ('13', '31', '23', '29', '30', '18', '17')) and not exists (select * from orders where o_custkey = c_custkey)) as custsale group by cntrycode order by cntrycode;| https://chatgpt.com/c/677fa7f2-3c2c-8005-88a7-e01896ed6c52 |Single instance of customer, projection is missing|





# Setting Up the Database
## PostgreSQL Installation  

Follow the link https://www.postgresql.org/download/ to download and install the suitable distribution of the database for your platform. 

## Loading TPCH Data  

### Obtaining DBGEN
1. Open the TPC webpage following the link: https://www.tpc.org/tpc_documents_current_versions/current_specifications5.asp  
2. In the `Active Benchmarks` table (first table), follow the link of `Download TPC-H_Tools_v3.0.1.zip`, it'll redirect to `TPC-H Tools Download
` page   
3. Give your details and click `download`, it'll email you the download link. Use the link to download the zip file.  
4. Unzip the zip file, and it must have the `dbgen` folder among the extracted contents  

### Prepare TPCH data on PostgreSQL using DBGEN
1. Download the code `tpch-pgsql` from the link: [https://github.com/Data-Science-Platform/tpch-pgsql/tree/master](https://github.com/ahanapradhan/tpch-pgsql).  
2. Follow the `tpch-pgsql` project Readme to prepare and load the data.  
3. (In case the above command gives error as `malloc.h` not found, showing the filenames, go inside dbgen folder, open the file and replace `malloc.h` with `stdlib.h`)

## Sample TPCH Data  
TPCH 100MB (sf=0.1) data is provided at: https://github.com/ahanapradhan/UnionExtraction/blob/master/mysite/unmasque/test/experiments/data/tpch_tiny.zip  
The load.sql file in the folder needs to be updated with the corresponding location of the data .csv files.

## Loading TPCH Data using DuckDB
https://duckdb.org/docs/extensions/tpch.html

# Setting up IDE
A developement environment for python project is required next. Here is the link to PyCharm Community Edition: https://www.jetbrains.com/pycharm/download/  (Any other IDE is also fine)

### Requirements
* Python 3.8.0 or above
* `django==4.2.4`
* `sympy==1.4`
* `psycopg2==2.9.3`
* `numpy==1.22.4`

# Setting Up the Code

The code is organized into the following directories:  

## mysite

The `mysite` directory contains the main project code.

### unmasque

Inside `unmasque`, you'll find the following subdirectories:

#### src

The `src` directory contains code that has been refactored from the original codebase developed in various theses, as well as newly written logic, often designed to simplify existing code. This may include enhancements or entirely new functionality.

#### test

The `test` directory houses unit test cases for each extractor module. These tests are crucial for ensuring the reliability and correctness of the code.

Please explore the individual directories for more details on the code and its purpose.

# Usage

## Configuration
inside `mysite` directory, there are two files as follows:  
pkfkrelations.csv --> contains key details for the TPCH schema. If any other schema is to be used, change this file accordingly.
config.ini --> This contains database login credentials and flags for optional features. Change the fields accordingly.  

### Config File Details:
`database` section: set your database credentials.  

`support` section: give support file name. The support file should be present in the same directory of this config file.

`logging` section: set logging level. The developer mode is `DEBUG`. Other valid levels are `INFO`, `ERROR`.

`feature` section: set flags for advanced features, as the flag names indicate. Included features are, `UNION`, `OUTER JOIN`, `<>` or `!=` operator in arithmetic filter predicates and `IN` operator. 

`options` section: extractor options. E.g. the maximum value for `LIMIT` clause is 1000. If the user needs to set a higher value, use `limit=value`.


### Running Unmasque
Open `mysite/unmasque/src/main_cmd.py` file.  
This script has one default input specified.  
Change this query to try Unmasque for various inputs.  
`test.util` package has `queries.py` file, containing a few sample queries. Any of them can be used for testing.

#### From Command Line:
Change the current directory to `mysite`.
Use the following command:  
`python -m unmasque.src.main_cmd` 

#### From IDE:
the `main` function in main_cmd.py can be run from the IDE.  

(Current code uses relative imports in main_cmd.py script. If that causes import related error while trying to run from IDE, please change the imports to absolute.)

#### From GUI:
In the terminal, go inside `unmasque` folder and start the Django app using the command: `python3 manage.py runserver`
Once the server is up at the 8080 port of localhost, the GUI can be accessed through the link: `http://localhost:8080/unmasque/`

