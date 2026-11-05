import unittest
from datetime import date
from flask import Flask
from app.extensions import db
from app.models.sales_stock_composition_analysis import SalesStockCompositionAnalysisSnapshot as S
from app.services.sales_stock_composition_analysis_for_purchase_plan import fetch_purchase_plan_composition_data as calculate


class ShopWeightTurnTests(unittest.TestCase):
    def test_location_factors_denominators_null_zero_cutoff_and_projection(self):
        app=Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI']='sqlite:///:memory:'
        db.init_app(app)
        with app.app_context():
            S.__table__.create(db.engine)
            first=S(id=1,branch_id=1,date=date(2026,9,30),min_trans_date=date(2026,4,1),
                section='CHAIN',gross_weight=100,provision_weight=10,inshop_weight=25)
            second=S(id=2,branch_id=2,date=date(2026,10,1),min_trans_date=date(2026,4,1),
                section='BANGLE',gross_weight=200,provision_weight=20,inshop_weight=50)
            db.session.add_all([first,second]);db.session.commit()
            result=calculate(None,{},sort_by='shop_weight_turn',sort_order='desc')
            annual=100*365/183+200*365/184
            self.assertAlmostEqual(result['total']['shop_weight_turn'],annual/75)
            self.assertAlmostEqual(result['total']['weight_turn'],annual/30)
            self.assertEqual(result['total']['inshop_weight'],75)
            self.assertEqual(result['stats']['inshop_weight'],75)
            self.assertAlmostEqual(result['stats']['shop_weight_turn'],annual/75)
            drill=calculate(None,{},path=['CHAIN'])
            self.assertAlmostEqual(drill['rows'][0]['shop_weight_turn'],100*365/183/25)
            cutoff=calculate(date(2026,9,30),{})
            self.assertEqual(cutoff['total']['inshop_weight'],25)
            second.inshop_weight=None;db.session.commit()
            missing=calculate(None,{})
            self.assertIsNone(missing['total']['shop_weight_turn'])
            self.assertIsNone(missing['stats']['inshop_weight'])
            self.assertIsNone(missing['stats']['shop_weight_turn'])
            self.assertIsNotNone(missing['total']['weight_turn'])
            second.inshop_weight=0;db.session.commit()
            zero=calculate(None,{'branch_id':['2']})
            self.assertIsNone(zero['rows'][0]['shop_weight_turn'])
            second.inshop_weight=50;second.min_trans_date=date(2026,5,1);db.session.commit()
            late=calculate(None,{'branch_id':['2']})
            projected = 200 * 335 / 154
            self.assertTrue(late['rows'][0]['includes_projection'])
            self.assertAlmostEqual(late['rows'][0]['shop_weight_turn'], projected / 50)
            self.assertAlmostEqual(late['total']['weight_turn'], projected / 20)
            self.assertEqual(late['stats']['location_factors'][0]['projected_days'], 335)
            mixed = calculate(None, {})
            by_section = {row['label']: row for row in mixed['rows']}
            self.assertFalse(by_section['CHAIN']['includes_projection'])
            self.assertAlmostEqual(by_section['CHAIN']['shop_weight_turn'], 100 * 365 / 183 / 25)
            self.assertTrue(mixed['stats']['includes_projection'])
            self.assertAlmostEqual(mixed['stats']['shop_weight_turn'], (100 * 365 / 183 + projected) / 75)
            db.session.remove()


if __name__=='__main__':
    unittest.main()
