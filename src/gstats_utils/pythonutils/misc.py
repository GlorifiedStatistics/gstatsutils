"""
Miscellaneous functions that don't have a set home
"""
import time
from threading import Thread
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from typing import Callable, Union, TypeVar, Optional, Any
    from typing_extensions import ParamSpec, Self


    TimeoutReturnType = TypeVar("TimeoutReturnType")
    TimeoutErrReturnType = TypeVar("TimeoutErrReturnType")
    TimeoutParamSpec = ParamSpec("TimeoutParamSpec")


class _TimeoutFuncThread(Thread):
    """
    A simple Thread class to call the passed function with passed args/kwargs
    """
    def __init__(self: 'Self', func: 'Callable[TimeoutParamSpec, TimeoutReturnType]', *args: 'TimeoutParamSpec.args', **kwargs: 'TimeoutParamSpec.kwargs'):
        """
        :param func: the function to call
        :param args: *args to pass to function when calling
        :param kwargs: **kwargs to pass to function when calling
        """
        super().__init__()
        self._func, self._args, self._kwargs = func, args, kwargs
        self._return = None
    
    def run(self: 'Self') -> 'None':
        """
        This should never be called. Instead, call TimeoutFuncThread.start() to start thread
        """
        self._return = self._func(*self._args, **self._kwargs)


def timeout_wrapper(func: 'Callable[TimeoutParamSpec, TimeoutReturnType]', timeout: 'float' = 3, timeout_ret_val: 'Any' = None):
    """
    Wraps a function to allow for timing-out after the specified time. If the function has not completed after timeout
        seconds, then the function will be terminated.
    """
    
    def wraped_func(*args: 'TimeoutParamSpec.args', **kwargs: 'TimeoutParamSpec.kwargs') -> 'Union[TimeoutReturnType, TimeoutErrReturnType]':
        thread = _TimeoutFuncThread(func, *args, **kwargs)
        thread.start()

        init_time = time.time()
        sleep_time = 1e-8
        while time.time() - init_time < timeout:
            if thread.is_alive():
                print("Sleeping for:", sleep_time)
                time.sleep(sleep_time)
                sleep_time = min(0.1, sleep_time * 1.05)
            else:
                return thread._return
        
        # If we make it here, there is an error, return value
        return timeout_ret_val
    
    return wraped_func
    