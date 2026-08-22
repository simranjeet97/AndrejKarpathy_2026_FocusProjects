from solution import RateLimiter
def test_hidden():
    rl = RateLimiter(1, 60); rl.allow(); assert rl.allow() == False
