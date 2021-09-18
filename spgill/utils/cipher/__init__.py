class VIG256(object):
    def __init__(self, key: bytes):
        """Initialize the cipher instance with a key."""
        self.key = key
        self.keyLen = len(key)
        self.resetCounter()

    def resetCounter(self):
        self.counter = 0

    def encryptChunk(self, chunk: bytes) -> bytes:
        chunkLen = len(chunk)
        chunkOut = bytearray()
        for i, value in enumerate(chunk):
            keyValue = self.key[(self.counter + i) % self.keyLen]
            chunkOut.append((value + keyValue) % 256)
        self.counter += chunkLen
        return chunkOut

    def decryptChunk(self, chunk: bytes) -> bytes:
        chunkLen = len(chunk)
        chunkOut = bytearray()
        for i, value in enumerate(chunk):
            keyValue = self.key[(self.counter + i) % self.keyLen]
            chunkOut.append((value - keyValue + 256) % 256)
        self.counter += chunkLen
        return chunkOut


testinput = b"                                                "

print("INPUT:", testinput)

c = VIG256(b"testestest")
middle = c.encryptChunk(testinput)

print("MIDDLE", middle)

c.resetCounter()
output = c.decryptChunk(middle)

print("OUTPUT", output)

print("SUCCESS?", testinput == output)
