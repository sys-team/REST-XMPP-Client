
# -*- coding: utf-8 -*-
__author__ = 'v.kovtash@gmail.com'

import hashlib
import hmac


hash_func = hashlib.sha1
hash_size = hash_func().digest_size


def digest(input_string):
    return hash_func(input_string).hexdigest()


def digest_size():
    return hash_size


def hex_digest_size():
    return hash_size * 2


def compare_digest(token1, token2):
    try:
        return hmac.compare_digest(token1, token2)
    except AttributeError:
        return compare_digest_fallback(token1, token2)


def compare_digest_fallback(x, y):
    if not (isinstance(x, str) and isinstance(y, str)):
        raise TypeError("both inputs should be instances of str")

    if len(x) != len(y):
        return False
    
    result = 0
    for a, b in zip(x, y):
        result |= (a != b)
    return result == 0
