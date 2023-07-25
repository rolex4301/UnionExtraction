from mysite.unmasque.refactored.abstract.ExtractorBase import Base
from mysite.unmasque.refactored.from_clause import FromClause
from mysite.unmasque.refactored.util.common_queries import alter_table_rename_to, create_table_like, drop_table
from mysite.unmasque.refactored.util.utils import isQ_result_empty
from mysite.unmasque.src.mocks.database import Schema


class UN1FromClause(Schema, Base):
    relations = []

    def __init__(self, connectionHelper):
        super().__init__(connectionHelper, "Old Unmasque")
        self.comtabs = None
        self.fromtabs = None
        self.to_nullify = None
        self.fromClause = FromClause(connectionHelper)

    def get_relations(self):
        self.fromClause.init.doJob()
        return self.fromClause.all_relations

    def nullify_except(self, s_set):
        self.to_nullify = set(self.get_relations()).difference(s_set)
        self.to_nullify = self.to_nullify.difference(self.comtabs)
        for tab in self.to_nullify:
            self.connectionHelper.execute_sql([alter_table_rename_to(tab, str(tab + "1")),
                                               create_table_like(tab, str(tab + "1"))])

    def run_query(self, QH):
        return self.fromClause.app.doJob(QH)

    def revert_nullify(self):
        for tab in self.to_nullify:
            self.connectionHelper.execute_sql([drop_table(tab),
                                               alter_table_rename_to(str(tab + "1"), tab),
                                               drop_table(str(tab + "1"))])

    def get_partial_QH(self, QH):
        return self.doJob(QH)

    def isEmpty(self, Res):
        return isQ_result_empty(Res)

    def extract_params_from_args(self, args):
        return args[0]

    def doActualJob(self, args):
        QH = self.extract_params_from_args(args)
        fromTabQ = set(self.get_fromTabs(QH))
        comTabQ = set(self.get_comTabs(QH))
        partTabQ = fromTabQ.difference(comTabQ)
        return partTabQ

    def get_fromTabs(self, QH):
        if self.fromtabs is None:
            self.fromtabs = self.fromClause.doJob([QH, "error"])
        return self.fromtabs

    def get_comTabs(self, QH):
        if self.comtabs is None:
            self.comtabs = self.fromClause.doJob([QH, "rename"])
        return self.comtabs
