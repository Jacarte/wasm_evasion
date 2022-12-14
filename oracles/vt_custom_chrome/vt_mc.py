import subprocess
import uuid
import hashlib

import os

class Storage(object):
    
    def __init__(self, endpoint, bucket, subfolder = "") -> None:
        raise NotImplementedError("Not implemented yet")


    def exists(self, key, local_cache=None):
        raise NotImplementedError("Not implemented yet")

    def save(self, key, content):
        raise NotImplementedError("Not implemented yet")


    def savefile(self, key, file):
        raise NotImplementedError("Not implemented yet")

    def saveb(self, key, content):
        raise NotImplementedError("Not implemented yet")

    def load(self, key):
        raise NotImplementedError("Not implemented yet")
    

    def loadfolder(self, localname,  key):
        raise NotImplementedError("Not implemented yet")

    def remove(self,  key):
        raise NotImplementedError("Not implemented yet")


class LocalWrapper(Storage):
    def __init__(self, endpoint) -> None:
        self.endpoint = endpoint

    def exists(self, key, local_cache=None):
        return os.path.exists(f"{self.endpoint}/{key}")

    def save(self, key, content):
        os.makedirs(os.path.dirname(f"{self.endpoint}/{key}"), exist_ok=True)
        f = open(f"{self.endpoint}/{key}", "w")
        f.write(content)
        f.close()

    def savefile(self, key, file):
        os.makedirs(os.path.dirname(f"{self.endpoint}/{key}"), exist_ok=True)
        f = open(f"{self.endpoint}/{key}", "w")
        f.write(file)
        f.close()

    def saveb(self, key, content):
        os.makedirs(os.path.dirname(f"{self.endpoint}/{key}"), exist_ok=True)
        f = open(f"{self.endpoint}/{key}", "wb")
        f.write(content)
        f.close()

    def load(self, key):
        f = open(f"{self.endpoint}/{key}", "r")
        content = f.read()
        f.close()
        return content, key



class MCWrapper(Storage):

    def __init__(self, endpoint, bucket, subfolder = "", local_cache=None) -> None:
        self.bucket = bucket
        self.endpoint = endpoint
        self.subfolder = subfolder
        self.local_cache = local_cache

        if self.subfolder:
            self.bucket = f"{self.bucket}/{self.subfolder}"


    def exists(self, key):
        if self.local_cache:
            return os.path.exists(f"{self.local_cache}/{key}")

        ch = subprocess.check_output(
            [ "mc", "ls", f"{self.endpoint}/{self.bucket}/{key}" ]
        )
        return len(ch) > 0

    def save(self, key, content):
        tmpname = uuid.uuid4().hex
        f = open(f"/tmp/{tmpname}", 'w')
        f.write(content)
        f.close()

        subprocess.check_output(
            [ "mc", "cp", f"/tmp/{tmpname}", f"{self.endpoint}/{self.bucket}/{key}" ]
        )
        print("File saved")


    def remove(self, key):
        
        subprocess.check_output(
            [ "mc", "rm", f"{self.endpoint}/{self.bucket}/{key}" ]
        )
        print(f"File removed", f"{self.endpoint}/{self.bucket}/{key}")


    def savefile(self, key, file):

        subprocess.check_output(
            [ "mc", "cp", file, f"{self.endpoint}/{self.bucket}/{key}" ]
        )
        print("File saved")

    def saveb(self, key, content):
        tmpname = uuid.uuid4().hex
        f = open(f"/tmp/{tmpname}", 'wb')
        f.write(content)
        f.close()

        subprocess.check_output(
            # TODO Add overwrite as an option
            [ "mc", "cp", f"/tmp/{tmpname}", f"{self.endpoint}/{self.bucket}/{key}" ]
        )

        print("File saved")


    def load(self, key):
        if self.local_cache:
            try:
                content = open(f"{self.local_cache}/{key}", 'rb').read()
                hsh = hashlib.sha256(content).hexdigest()
                print("File loaded")
                return content, hsh
            except Exception as e:
                print("Failed to load from local", e)

        tmpname = uuid.uuid4().hex
        tmpnmame = f"/tmp/{tmpname}"

        subprocess.check_output(
            [ "mc", "cp",  f"{self.endpoint}/{self.bucket}/{key}", tmpnmame]
        )

        content = open(tmpnmame, 'rb').read()
        hsh = hashlib.sha256(content).hexdigest()

        print("File loaded")
        return content, hsh

    

    def loadfolder(self, localname,  key):

        subprocess.check_output(
            [ "mc", "mirror", f"{self.endpoint}/{self.bucket}/{key}", localname, "--overwrite"]
        )
        print("Folder loaded")



if __name__ == "__main__":

    wrap = MCWrapper("exp", "my-bucket")
    if wrap.exists("data/mutate_datas/2114.ru.wasm/all.zip"): print("Exist")
    if not wrap.exists("data/mutate_datas/21.zip"): print("Not exist")
    # partial address
    if wrap.exists("data/mutate_datas/2114.ru.wasm"): print("Exist")

    c = wrap.load("data/mutate_datas/2114.ru.wasm/all.zip")
    print(len(c))

    wrap.save("data/mutate_datas/2114.ru.wasm/tt/t1.txt", "Hello")
    wrap.loadfolder("./tmp", "data/mutate_datas/2114.ru.wasm/tt")
    c = wrap.load("data/mutate_datas/2114.ru.wasm/tt/t1.txt")

    print(c)