import subprocess
import os
import sys
import threading
import time
import signal
from typing import Optional, Dict, List, Union, Tuple
from dataclasses import dataclass


@dataclass
class CommandResult:
    """Data class to hold command execution results"""
    stdout: str
    stderr: str
    return_code: int
    command: str
    success: bool
    execution_id: Optional[str] = None

    def __str__(self):
        id_str = f" (ID: {self.execution_id})" if self.execution_id else ""
        return f"Command{id_str}: {self.command}\nReturn Code: {self.return_code}\nSuccess: {self.success}\nOutput: {self.stdout[:100]}..."


@dataclass
class RunningProcess:
    """Data class to hold information about a running process"""
    process: subprocess.Popen
    command: str
    start_time: float
    thread: Optional[threading.Thread] = None


class CMDExecuter:
    """
    A utility class to simplify command line execution from Python.
    Provides methods for running shell commands with process management and cancellation.
    """

    def __init__(self, default_timeout: int = 0, default_shell: bool = True):
        """
        Initialize the CMDExecuter

        Args:
            default_timeout: Default timeout for commands in seconds (0 or negative means no timeout)
            default_shell: Whether to use shell by default
        """
        self.default_timeout = default_timeout
        self.default_shell = default_shell
        self.last_result: Optional[CommandResult] = None
        self.running_processes: Dict[str, RunningProcess] = {}
        self._lock = threading.Lock()

    def execute(self,
                execution_id: str,
                command: Union[str, List[str]],
                timeout: Optional[int] = None,
                shell: Optional[bool] = None,
                capture_output: bool = True,
                text: bool = True,
                cwd: Optional[str] = None,
                env: Optional[Dict[str, str]] = None,
                raise_on_error: bool = False,
                async_execution: bool = False) -> CommandResult:
        """
        Execute a command with a unique ID for process management

        Args:
            execution_id: Unique identifier for this execution
            command: Command to execute (string or list)
            timeout: Timeout in seconds (None for default, 0 or negative for no timeout)
            shell: Whether to use shell (None to use default)
            capture_output: Whether to capture stdout/stderr
            text: Whether to return text (True) or bytes (False)
            cwd: Working directory for the command
            env: Environment variables
            raise_on_error: Whether to raise exception on non-zero exit code
            async_execution: Whether to run asynchronously and return immediately

        Returns:
            CommandResult object with execution details
        """
        if execution_id in self.running_processes:
            raise ValueError(f"Execution ID '{execution_id}' is already in use")

        if timeout is None:
            timeout = self.default_timeout
        if shell is None:
            shell = self.default_shell

        # If timeout is 0 or negative, don't use timeout
        actual_timeout = timeout if timeout and timeout > 0 else None

        try:
            # Set up process group for proper cleanup of pipelines
            if sys.platform != "win32":
                # On Unix-like systems, create a new process group
                process = subprocess.Popen(
                    command,
                    shell=shell,
                    stdout=subprocess.PIPE if capture_output else None,
                    stderr=subprocess.PIPE if capture_output else None,
                    text=text,
                    cwd=cwd,
                    env=env,
                    preexec_fn=os.setsid  # Create new session/process group
                )
            else:
                # On Windows, use CREATE_NEW_PROCESS_GROUP
                process = subprocess.Popen(
                    command,
                    shell=shell,
                    stdout=subprocess.PIPE if capture_output else None,
                    stderr=subprocess.PIPE if capture_output else None,
                    text=text,
                    cwd=cwd,
                    env=env,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )

            # Register the running process
            with self._lock:
                self.running_processes[execution_id] = RunningProcess(
                    process=process,
                    command=str(command),
                    start_time=time.time()
                )

            if async_execution:
                # For async execution, start a thread to handle completion
                def handle_async_completion():
                    try:
                        stdout, stderr = process.communicate(timeout=actual_timeout)
                        self._cleanup_process(execution_id)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        stdout, stderr = process.communicate()
                        self._cleanup_process(execution_id)
                    except Exception:
                        self._cleanup_process(execution_id)

                thread = threading.Thread(target=handle_async_completion, daemon=True)
                thread.start()

                with self._lock:
                    self.running_processes[execution_id].thread = thread

                # Return immediately for async execution
                return CommandResult(
                    stdout="",
                    stderr="",
                    return_code=-999,  # Special code for async/running
                    command=str(command),
                    success=False,
                    execution_id=execution_id
                )
            else:
                # Synchronous execution
                try:
                    stdout, stderr = process.communicate(timeout=actual_timeout)

                    cmd_result = CommandResult(
                        stdout=stdout if capture_output else "",
                        stderr=stderr if capture_output else "",
                        return_code=process.returncode,
                        command=str(command),
                        success=process.returncode == 0,
                        execution_id=execution_id
                    )

                    self.last_result = cmd_result
                    self._cleanup_process(execution_id)

                    if raise_on_error and not cmd_result.success:
                        raise subprocess.CalledProcessError(
                            cmd_result.return_code,
                            command,
                            cmd_result.stdout,
                            cmd_result.stderr
                        )

                    return cmd_result

                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout, stderr = process.communicate()
                    self._cleanup_process(execution_id)

                    timeout_msg = f"Command timed out after {timeout} seconds" if actual_timeout else "Command timed out"
                    cmd_result = CommandResult(
                        stdout=stdout if capture_output else "",
                        stderr=timeout_msg,
                        return_code=-1,
                        command=str(command),
                        success=False,
                        execution_id=execution_id
                    )
                    self.last_result = cmd_result

                    if raise_on_error:
                        raise

                    return cmd_result

        except Exception as e:
            self._cleanup_process(execution_id)
            cmd_result = CommandResult(
                stdout="",
                stderr=str(e),
                return_code=-1,
                command=str(command),
                success=False,
                execution_id=execution_id
            )
            self.last_result = cmd_result

            if raise_on_error:
                raise

            return cmd_result

    def stop(self, execution_id: str, force: bool = False) -> bool:
        """
        Stop a running command by its execution ID
        For pipelines, this will stop the entire process group

        Args:
            execution_id: ID of the execution to stop
            force: Whether to force kill (True) or terminate gracefully (False)

        Returns:
            True if process was stopped, False if not found or already finished
        """
        with self._lock:
            if execution_id not in self.running_processes:
                return False

            running_process = self.running_processes[execution_id]

        try:
            if running_process.process.poll() is None:  # Process is still running
                if sys.platform != "win32":
                    # On Unix-like systems, kill the entire process group
                    try:
                        if force:
                            os.killpg(os.getpgid(running_process.process.pid), 9)  # SIGKILL
                        else:
                            os.killpg(os.getpgid(running_process.process.pid), 15)  # SIGTERM
                    except ProcessLookupError:
                        # Process group doesn't exist anymore, try individual process
                        if force:
                            running_process.process.kill()
                        else:
                            running_process.process.terminate()
                    except OSError:
                        # Fallback to individual process termination
                        if force:
                            running_process.process.kill()
                        else:
                            running_process.process.terminate()
                else:
                    # On Windows, use TerminateProcess on the process group
                    if force:
                        running_process.process.kill()
                    else:
                        running_process.process.terminate()

                # Wait a bit for graceful termination
                if not force:
                    try:
                        running_process.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        # If graceful termination failed, force kill
                        if sys.platform != "win32":
                            try:
                                os.killpg(os.getpgid(running_process.process.pid), 9)
                            except (ProcessLookupError, OSError):
                                running_process.process.kill()
                        else:
                            running_process.process.kill()

                self._cleanup_process(execution_id)
                return True
            else:
                # Process already finished
                self._cleanup_process(execution_id)
                return False

        except Exception:
            self._cleanup_process(execution_id)
            return False

    def is_running(self, execution_id: str) -> bool:
        """
        Check if a command is still running

        Args:
            execution_id: ID of the execution to check

        Returns:
            True if still running, False otherwise
        """
        with self._lock:
            if execution_id not in self.running_processes:
                return False

            running_process = self.running_processes[execution_id]
            is_alive = running_process.process.poll() is None

            if not is_alive:
                self._cleanup_process(execution_id)

            return is_alive

    def get_running_processes(self) -> Dict[str, Dict[str, Union[str, float]]]:
        """
        Get information about all currently running processes

        Returns:
            Dictionary with execution_id as key and process info as value
        """
        result = {}
        with self._lock:
            for exec_id, running_process in self.running_processes.copy().items():
                if running_process.process.poll() is None:
                    result[exec_id] = {
                        'command': running_process.command,
                        'start_time': running_process.start_time,
                        'duration': time.time() - running_process.start_time,
                        'pid': running_process.process.pid
                    }
                else:
                    # Clean up finished processes
                    self._cleanup_process(exec_id)

        return result

    def stop_all(self, force: bool = False) -> int:
        """
        Stop all running processes

        Args:
            force: Whether to force kill all processes

        Returns:
            Number of processes that were stopped
        """
        with self._lock:
            execution_ids = list(self.running_processes.keys())

        stopped_count = 0
        for exec_id in execution_ids:
            if self.stop(exec_id, force):
                stopped_count += 1

        return stopped_count

    def wait_for_completion(self, execution_id: str, timeout: Optional[int] = None) -> Optional[CommandResult]:
        """
        Wait for a specific execution to complete and return its result

        Args:
            execution_id: ID of the execution to wait for
            timeout: Maximum time to wait in seconds

        Returns:
            CommandResult if process completes, None if timeout or not found
        """
        with self._lock:
            if execution_id not in self.running_processes:
                return None
            running_process = self.running_processes[execution_id]

        try:
            stdout, stderr = running_process.process.communicate(timeout=timeout)

            cmd_result = CommandResult(
                stdout=stdout or "",
                stderr=stderr or "",
                return_code=running_process.process.returncode,
                command=running_process.command,
                success=running_process.process.returncode == 0,
                execution_id=execution_id
            )

            self._cleanup_process(execution_id)
            return cmd_result

        except subprocess.TimeoutExpired:
            return None
        except Exception:
            self._cleanup_process(execution_id)
            return None

    def _cleanup_process(self, execution_id: str):
        """Internal method to clean up finished processes"""
        with self._lock:
            if execution_id in self.running_processes:
                del self.running_processes[execution_id]

    def is_command_available(self, command: str) -> bool:
        """
        Check if a command is available on the system

        Args:
            command: Command name to check

        Returns:
            True if command is available, False otherwise
        """
        import uuid
        temp_id = str(uuid.uuid4())

        if sys.platform == "win32":
            check_cmd = f"where {command}"
        else:
            check_cmd = f"which {command}"

        result = self.execute(temp_id, check_cmd)
        return result.success

    def get_last_result(self) -> Optional[CommandResult]:
        """Get the result of the last executed command"""
        return self.last_result

    def print_last_result(self):
        """Print details of the last executed command"""
        if self.last_result:
            print(self.last_result)
        else:
            print("No commands have been executed yet")

