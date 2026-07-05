def test_palindrome():
    assert is_palindrome("racecar") == True
    assert is_palindrome("hello") == False
    assert is_palindrome("madam") == True
    assert is_palindrome("step on no pets") == True

def is_palindrome(s):
    s = s.replace(" ", "").lower()
    return s == s[::-1]