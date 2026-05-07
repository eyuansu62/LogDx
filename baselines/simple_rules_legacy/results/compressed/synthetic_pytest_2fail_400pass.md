# CI Log (compressed)

**Sections:** 2 total, 2 with failures

## Failures

### ❌ Run pytest `[pytest]` (orig 441 lines, id=s_6f164c4e)
```
============================= test session starts ==============================
platform linux -- Python 3.11.4, pytest-7.4.0, pluggy-1.3.0
rootdir: /home/runner/work/myproject/myproject
plugins: cov-4.1.0, xdist-3.3.1, anyio-3.7.1
collected 402 items
=================================== FAILURES ===================================
____________________________ test_token_expiry ____________________________
    def test_token_expiry():
        token = generate_token(ttl=3600)
        time.sleep(0.1)
>       assert validate(token).is_valid is True
E       AssertionError: assert False is True
E        +  where False = <TokenResult valid=False expired=True>.is_valid
tests/test_auth.py:42: AssertionError
_______________________ test_refund_idempotent _________________________
    def test_refund_idempotent():
        charge = create_charge(amount=1000)
        r1 = refund(charge.id)
>       r2 = refund(charge.id)
tests/test_billing.py:87: 
_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _
    def refund(charge_id):
        if _refunded.get(charge_id):
>           raise DuplicateRefundError(charge_id)
E           myapp.errors.DuplicateRefundError: ch_abc123
src/myapp/billing.py:117: DuplicateRefundError
=========================== short test summary info ============================
FAILED tests/test_auth.py::test_token_expiry - AssertionError: assert False is True
FAILED tests/test_billing.py::test_refund_idempotent - myapp.errors.DuplicateRefundError: ch_abc123
================== 2 failed, 400 passed, 3 warnings in 47.21s ==================
```

### ❌ _between_groups `[generic]` (orig 1 lines, id=s_d62553a2)
```
##[error]Process completed with exit code 1.
```
