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
import sys
import os

import sentry_sdk


logger = logging.getLogger(__name__)


class TaskFailedException(Exception):
    """Thrown if a task throws an unhandled exception."""
    pass


def task(function):
    """
    Execute the given function in a child process.

    Use this as a decorator on a function to make sure it's called in a forked
    process. The return value of the process will be passed through a pipe, and
    so is subject to the same restrictions[1], namely, the object must be
    pickleable and not too large (approximately 32 MiB+).

    If the child process throws an exception, it will be logged, reported to Sentry, the
    database status will be updated and `TaskFailedException` will be raised.

    [1] https://docs.python.org/3/library/multiprocessing.html#multiprocessing.connection.Connection.send
    """

    def runner(pipe, job, *args, **kwargs):
        # This is the function called in a new process.
        # Sentry needs to be initialized here (in addition to the main process).
        sentry_sdk.init(dsn=os.environ.get("SENTRY_DSN"))
        # Call the wrapped function with the given arguments and pass the return value
        # back through a pipe.
        try:
            retval = function(job, *args, **kwargs)
        except Exception as exception:
            # TODO: update db state
            logger.exception(exception)
            sentry_sdk.capture_exception(exception)
            # Wait for the sentry event to be sent; otherwise we'd exit the process too
            # soon.
            sentry_sdk.flush()
            sys.exit(-1)
        else:
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
        if process.exitcode != 0:
            raise TaskFailedException()
        # Return the piped data back to the caller.
        return pipe_in.recv()

    return wrapper
