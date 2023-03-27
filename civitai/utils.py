# -*- coding: utf-8 -*-

import os


async def check_file_exists(dir: str, fn: str, split_ext: bool = False) -> bool:
    fn = fn.split(os.path.sep)[-1]
    for _, _, efns in os.walk(dir):
        for efn in efns:
            if split_ext:
                if efn.rsplit(".", maxsplit=1)[0] == fn:
                    return True
            else:
                if efn == fn:
                    return True
    return False
