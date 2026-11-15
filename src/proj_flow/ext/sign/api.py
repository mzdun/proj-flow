# Copyright (c) 2025 Marcin Zdun
# This code is licensed under MIT license (see LICENSE for details)

"""
The **proj_flow.ext.sign.api** defines an extension point for per-platform
sign tools.
"""

import base64
import json
import os
from abc import ABC, abstractmethod
from typing import List, NamedTuple, Optional

from proj_flow import base
from proj_flow.api import env

ENV_KEY = "SIGN_TOKEN"


class Key(NamedTuple):
    """
    Signing key, decoded from the base64 fields of the signature JSON
    document.
    """

    #: Decoded ``token`` field.
    token: str
    #: Decoded ``secret`` field.
    secret: bytes


def _get_key_from_contents(key: str, rt: env.Runtime):
    try:
        obj = json.loads(key)
    except json.decoder.JSONDecodeError:
        rt.message("sign: the signature is not a valid JSON document")
        return None

    if not isinstance(obj, dict):
        rt.message("sign: the signature is missing required fields")
        return None

    token = obj.get("token")
    secret = obj.get("secret")
    if not isinstance(token, str) or not isinstance(secret, str):
        rt.message("sign: the signature is missing required fields")
        return None

    return Key(
        base64.b64decode(token).decode("UTF-8"),
        base64.b64decode(secret),
    )


def get_key(rt: env.Runtime) -> Optional[Key]:
    """
    Find the signing key. The first valid JSON document with base64
    ``token`` and ``secret`` fields is used, looking in the ``$SIGN_TOKEN``
    environment variable, then in ``./signature.key`` and finally in
    ``~/signature.key``.

    .. note::

        ``$SIGN_TOKEN`` holds the JSON document itself, not a path to a file
        with it.

    :param rt: runtime used for messages
    :returns: the key, or ``None``, if none was found
    """

    rt.message(f"sign: trying ${ENV_KEY}")
    env = os.environ.get(ENV_KEY)
    if env:
        key = _get_key_from_contents(env, rt)
        if key is not None:
            return key
    local_signature = os.path.join(".", "signature.key")
    home_signature = os.path.join(os.path.expanduser("~"), "signature.key")
    for filename in [local_signature, home_signature]:
        rt.message(f"sign: trying {filename}")
        if os.path.isfile(filename):
            with open(filename, encoding="UTF-8") as file:
                result = file.read().strip()
                key = _get_key_from_contents(result, rt)
                if key is not None:
                    return key

    rt.message("sign: no key set up")

    return None


class SigningTool(ABC):
    """
    Per-platform code signing tool, registered with :data:`signing_tool` and
    used by the Sign and SignPackages steps.
    """

    @abstractmethod
    def is_active(self, config: env.Config, rt: env.Runtime) -> bool:
        """
        Check, if this tool can sign anything in current run, e.g. if it runs
        on the right platform and has a key.

        :param config: config of current run
        :param rt: runtime used for messages
        """
        ...

    @abstractmethod
    def sign(self, config: env.Config, rt: env.Runtime, files: List[str]) -> None:
        """
        Sign the files in place.

        :param config: config of current run
        :param rt: runtime used for messages and running the tools
        :param files: paths of the files to sign, all accepted by
            :meth:`is_signable`
        :raises StepFailed: the files could not be signed
        """
        ...

    @abstractmethod
    def is_signable(self, filename: str, as_package: bool) -> bool:
        """
        Check, if this tool can sign the file.

        :param filename: path of the file
        :param as_package: the file is a package or an installer (from the
            SignPackages step), not a binary (from the Sign step)
        """
        ...


#: Registry of the code signing tools.
signing_tool = base.registry.Registry[SigningTool]("SigningTool")
