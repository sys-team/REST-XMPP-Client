
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
    return hmac.compare_digest(token1, token2)
