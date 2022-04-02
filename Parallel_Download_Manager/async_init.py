

def Async_init(cls):
    """
    Decorator that enables async object creation

    :param cls: The static class object used to make changes to the class (using decorator)
    :return: The class after the modifications
    """

    async def init(obj, *arg, **kwarg):
        await obj.__init__(*arg, **kwarg)
        return obj

    def new(cls1, *arg, **kwarg):
        obj = object.__new__(cls1)
        return init(obj, *arg, **kwarg)

    cls.__new__ = new
    return cls
