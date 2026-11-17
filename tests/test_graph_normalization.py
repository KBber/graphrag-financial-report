import unittest

from src.build_graph import normalize, uid_of


class GraphNormalizationTests(unittest.TestCase):
    def test_company_aliases_share_a_stock_code_and_uid(self):
        canonical = "宁德时代"
        alias = " 宁德时代新能源科技股份有限公司 "

        self.assertEqual(normalize(alias, "Company"), (canonical, "300750"))
        self.assertEqual(uid_of(alias, "Company"), uid_of(canonical, "Company"))

    def test_non_company_names_keep_their_entity_type(self):
        name = "宁德时代新能源科技股份有限公司"

        self.assertEqual(normalize(f" {name} ", "Product"), (name, None))
        self.assertEqual(uid_of(name, "Product"), f"Product:{name}")
