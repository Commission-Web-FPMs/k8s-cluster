"""Bounded scrypt verifier; preserve Werkzeug N=32768,r=8,p=1,64-byte digest."""
from django.contrib.auth.hashers import ScryptPasswordHasher

class CarteFedeScryptPasswordHasher(ScryptPasswordHasher):
    maxmem = 128 * 1024 * 1024
    work_factor = 32768
    block_size = 8
    parallelism = 1
