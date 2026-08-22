from solution import RateLimiter
def test_basic():
    rl = RateLimiter(2, 60); assert rl.allow() == True
