#!/usr/bin/env python
# Copyright (C) 2015 Dmitry Rodionov
# This file is part of my GSoC'15 project for Cuckoo Sandbox:
#	http://www.cuckoosandbox.org
# This software may be modified and distributed under the terms
# of the MIT license. See the LICENSE file for details.

import os
import json
from time import sleep
from sys import argv
from collections import namedtuple
from subprocess import Popen
from tempfile import NamedTemporaryFile
from .fileutils import filelines

syscall = namedtuple("syscall", "name args result errno timestamp pid")

def dtruss(target, **kwargs):
	"""Returns a list of syscalls made by a target.

	Every syscall is a named tuple with the following properties:
	name (string), args (list of strings), result (int), errno (int).
	"""

	if not target:
		raise Exception("Invalid target for dtruss()")

	file = NamedTemporaryFile()

	cmd = ["/bin/bash", _dtruss_script_path(), "-W", file.name, "-f"]
	# Add timeout
	if ("timeout" in kwargs) and (kwargs["timeout"] is not None):
		cmd += ["-K", str(kwargs["timeout"])]
	# Watch for a specific syscall only
	if "syscall" in kwargs:
		cmd += ["-t", kwargs["syscall"]]
	cmd += [_sanitize_target_path(target)]
	# Arguments for the target
	if "args" in kwargs:
		cmd += kwargs["args"]

	# The dtrace script will take care of timeout itself, so we just launch it asynchronously
	with open(os.devnull, "w") as f:
		handle = Popen(cmd, stdout=f, stderr=f)

	for entry in filelines(file):
		if "## dtruss.sh done ##" in entry.strip():
			break
		syscall = _parse_syscall(entry.strip())
		if syscall is not None:
			yield syscall
	file.close()

def _sanitize_target_path(path):
    return path.replace(" ", "\\ ")

def _dtruss_script_path():
    return os.path.dirname(os.path.abspath(__file__)) + "/dtruss.sh"

#
# Parsing implementation details
#

def _parse_syscall(string):
	string = string.replace("\\0", "")
	try:
		parsed = json.loads(string)
	except:
		return None

	name   = parsed["syscall"]
	args   = parsed["args"]
	result = parsed["retval"]
	errno  = parsed["errno"]
	pid    = parsed["pid"]
	timestamp = parsed["timestamp"]

	return syscall(name=name, args=args, result=result, errno=errno, pid=pid,
	               timestamp=timestamp)

if __name__ == "__main__":
	if len(argv) < 2:
		print "Usage: %s <target> [syscall]" % argv[0]
		exit(0)

	target = argv[1]
	optional_probe = argv[2] if len(argv) > 2 else None

	for syscall in dtruss(target, optional_probe):
		print "%s(%s) -> %#x %s" % (
			syscall.name,
			", ".join(syscall.args) if len(syscall.args) > 0 else "",
			syscall.result,
			"(errno = %s)" % syscall.errno if syscall.errno != 0 else ""
		)
