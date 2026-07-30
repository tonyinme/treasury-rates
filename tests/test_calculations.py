from datetime import date
import pytest
from app.calculations import *

SET=date(2026,2,15); MAT=date(2031,2,15)
def test_current_yield(): assert current_yield(.0475,95)==pytest.approx(.05)
def test_dirty_cash_yield(): assert cash_yield_dirty(.05,101)==pytest.approx(5/101)
def test_accrued_on_coupon_date(): assert accrued_interest(.04,MAT,SET)==pytest.approx(0)
def test_accrued_mid_period():
    assert accrued_interest(.04,date(2030,8,15),date(2026,5,15))==pytest.approx(1.0,abs=.03)
def test_coupon_income_and_face(): assert annual_coupon_income(100000,.0475)==4750
def test_face_purchased(): assert face_value_purchased(100000,80)==125000
def test_gain_loss(): assert gain_loss_to_par(100000,80)==20000
def test_ytm_par_bond(): assert yield_to_maturity(100,.04,MAT,SET)==pytest.approx(.04,abs=.0002)
def test_ytm_discount_bond(): assert yield_to_maturity(90,.04,MAT,SET)>.04
def test_ytm_premium_bond(): assert yield_to_maturity(110,.04,MAT,SET)<.04
def test_duration(): 
    y=yield_to_maturity(100,.04,MAT,SET); mac,mod=duration(y,100,.04,MAT,SET)
    assert 4 < mac < 5 and mod < mac
def test_near_maturity():
    mat=date(2026,8,15); y=yield_to_maturity(100,.04,mat,SET)
    assert y==pytest.approx(.04,abs=.001)
def test_matured_returns_none(): assert yield_to_maturity(100,.04,SET,SET) is None
def test_price_from_yield_par(): assert price_from_yield(.04,.04,MAT,SET)==pytest.approx(100,abs=.02)
