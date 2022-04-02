import unittest
import asyncio
import time
from Parallel_Download_Manager.async_init import Async_init


class test_Async_Object(unittest.IsolatedAsyncioTestCase):
    async def test_async_init(self):
        e = await E()
        print(e.b)  # 2
        print(e.a)  # 1

        print(f"started at {time.strftime('%X')}")
        task1 = asyncio.create_task(F())
        task2 = asyncio.create_task(C())
        f = await task1  # Prints F class
        c = await task2
        self.assertEqual(f.f, 6)
        self.assertEqual(c.a, 1)
        self.assertEqual(c.b, 2)
        self.assertEqual(c.c, 3)
        print(f"finished at {time.strftime('%X')}")

class A:
    def __init__(self):
        self.a = 1

class B(A):
    def __init__(self):
        self.b = 2
        super().__init__()

@Async_init
class C(B):
    async def __init__(self):
        print("switched")
        await asyncio.sleep(2)
        super().__init__()
        self.c = 3

@Async_init
class D:
    async def __init__(self, a):
        self.a = a

@Async_init
class E(D):
    async def __init__(self):
        self.b = 2
        await super().__init__(1)

@Async_init
class F:
    def __new__(cls):
        print(cls)
        return super().__new__(cls)

    async def __init__(self):
        print("sleeping")
        await asyncio.sleep(3)
        self.f = 6


if __name__ == '__main__':
    unittest.main(verbosity=2)
