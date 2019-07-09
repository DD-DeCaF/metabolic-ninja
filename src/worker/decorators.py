# Copyright (c) 2018, Novo Nordisk Foundation Center for Biosustainability,
# Technical University of Denmark.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import multiprocessing
import functools


logger = logging.getLogger(__name__)


def fork(function):
    """
    Execute the given function in a child process.

    Use this as a decorator on a function to make sure it's called in a forked
    process. The return value of the process will be passed through a pipe, and
    so is subject to the same restrictions[1], namely, the object must be
    pickleable and not too large (approximately 32 MiB+).

    [1] https://docs.python.org/3/library/multiprocessing.html#multiprocessing.connection.Connection.send
    """

    def runner(pipe, *args, **kwargs):
        # This is the function called in a new process. Call the wrapped
        # function with the given arguments and pass the return value back
        # through a pipe.
        retval = function(*args, **kwargs)
        pipe.send(retval)

    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        # Create a one-way pipe to pass the return value of the wrapped
        # function.
        logger.debug(f"Spawning new process for function: {function}")
        pipe_in, pipe_out = multiprocessing.Pipe(duplex=False)
        process = multiprocessing.Process(
            target=runner, args=(pipe_out,) + args, kwargs=kwargs
        )
        process.start()
        process.join()
        # Return the piped data back to the caller.
        return pipe_in.recv()

    return wrapper
