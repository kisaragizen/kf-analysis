import sys, os
from cryptography.fernet import Fernet

def dec(path, key):
    try: fernet = Fernet(key.encode())
    except Exception as e:
        print(f"invalid key: {e}")
        return False
    with open(path, 'rb') as fin:
        data = fin.read()
        decrypted = fernet.decrypt(data)
    out_path = path[:-4]
    with open(out_path, 'wb') as fout:
        fout.write(decrypted)
    print("decrypted:", path)
def enc(path, key):
    if not key:
        key = Fernet.generate_key()
    elif isinstance(key, str):
        key = key.encode()
    with open(path, 'rb') as fin:
        data = fin.read()
    fernet = Fernet(key)
    encrypted = fernet.encrypt(data)
    out_path = path + '.enc'
    with open(out_path, 'wb') as fout:
        fout.write(encrypted)
    print("encrypted:", out_path)
    return key.decode()

if __name__ == '__main__':
    filelist = sys.argv[1:]
    if any(os.path.isdir(path) for path in filelist):
        raise Exception("this function only works with files.")
    s0 = all(path[-4:]==".enc" for path in filelist)
    s1 = all(path[-4:]!=".enc" for path in filelist)
    if s0:
        key = input("please input the decrypt key: ")
        for x in filelist: dec(x, key)
        input("all files decrypted.")
    elif s1:
        key = None
        for x in filelist: key = enc(x, key)
        print(key)
        input("dont forget copy the decrypt key.")
    else:
        raise Exception("input files must be either all encrypted or all unencrypted.")
