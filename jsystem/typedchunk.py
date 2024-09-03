import struct
import pyaurum
from copy import deepcopy
"""
TypedChunk
Abstract chunk that allows for packing and unpacking to JSON and bytes.
"""
class TypedChunk():
    # Initialize Typed Chunk
    def __init__(self, name, default_val = None):
        self.name = name
        self.val = default_val
        self.size = 0
        
    def unpack(self, buffer, offset: int = 0):
        raise "NotYetImplemented"
    # Add data to json object
    def pack_json(self, obj: dict):
        obj[self.name] = self.val
    def pack(self) -> bytes:
        raise "NotYetImplemented"
    def unpack_json(self, entry):
        raise "NotYetImplemented"
    def get_val(self): 
        return self.val
    def get_size(self):
        return self.size
    
class U8Chunk(TypedChunk):
    def unpack(self, buffer, offset: int = 0):
        self.val = pyaurum.get_u8(buffer, offset)
        self.size = 1
    def pack(self) -> bytes:
        return pyaurum.pack_u8(self.val)
    def unpack_json(self, entry):
        self.val = entry[self.name]
        self.size = 1

class S8Chunk(TypedChunk):
    def unpack(self, buffer, offset: int = 0):
        self.val = pyaurum.get_s8(buffer, offset)
        self.size = 1
    def pack(self) -> bytes:
        return pyaurum.pack_s8(self.val)
    def unpack_json(self, entry):
        self.val = entry[self.name]
        self.size = 1
        

class U16Chunk(TypedChunk):
    def unpack(self, buffer, offset: int = 0):
        self.val = pyaurum.get_u16(buffer, offset)
        self.size = 2
    def pack(self) -> bytes:
        return pyaurum.pack_u16(self.val)
    def unpack_json(self, entry):
        self.val = entry[self.name]
        self.size = 2
        

class U32Chunk(TypedChunk):
    def unpack(self, buffer, offset: int = 0):
        self.val = pyaurum.get_u32(buffer, offset)
        self.size = 4
    def pack(self) -> bytes:
        return pyaurum.pack_u32(self.val)
    def unpack_json(self, entry):
        self.val = entry[self.name]
        self.size = 4
        

class U32ChunkBytes(TypedChunk):
    def unpack(self, buffer, offset: int = 0):
        self.val = buffer[offset:offset + 4]
        self.size = 4
    def pack(self) -> bytes:
        return self.val
    def pack_json(self, obj: dict):
        obj[self.name] = self.val.hex()
    def unpack_json(self, entry):
        self.val = bytes.fromhex(entry[self.name])
        self.size = 4
        

class F32Chunk(TypedChunk):
    def unpack(self, buffer, offset: int = 0):
        self.val = pyaurum.get_f32(buffer, offset)
        self.size = 4
    def pack(self) -> bytes:
        return pyaurum.pack_f32(self.val)
    def unpack_json(self, entry):
        self.val = entry[self.name]
        self.size = 4
        
class BoolChunk(TypedChunk):
    def unpack(self, buffer, offset: int = 0):
        self.val = pyaurum.get_bool(buffer, offset)
        self.size = 1
    def pack(self) -> bytes:
        ret = pyaurum.pack_bool(self.val)
        return ret
    def unpack_json(self, entry):
        self.val = entry[self.name]
        self.size = 1

# offsets are necessary for the dynamic way chunks are unpacked and repacked
class Offset(TypedChunk):
    def __init__(self, size):
        self.size = size
        self.val = None
    def pack(self):
        return bytes('\0' * self.size, "ascii")
    def unpack(self, buffer, offset):
        pass
    def unpack_json(self, entry):
        pass
    def pack_json(self, obj):
        pass

# Chunk that only appears under a condition.
class ConditionalChunk(TypedChunk):
    def __init__(self, chunk: TypedChunk):
        super().__init__("")
        self.chunk = chunk
    def unpack(self, buffer, offset):
        if (self.is_condition_met()):
            self.chunk.unpack(buffer, offset)

    def pack(self) -> bytes:
        if (self.is_condition_met()):
            return self.chunk.pack()
    def unpack_json(self, entry):
        if (self.is_condition_met()):
            self.chunk.unpack_json(entry)
    def pack_json(self, obj: dict):
        if (self.is_condition_met()):
            return self.chunk.pack_json(obj)
    def is_condition_met(self) -> bool:
        return True
    def get_size(self):
        return self.chunk.get_size()
    def get_val(self):
        return self.chunk.get_val()
    
class FlagConditionalChunk(ConditionalChunk):
    def __init__(self, chunk: TypedChunk, flag, flag_num):
        super().__init__(chunk)
        self.flag = flag
        self.flag_num = flag_num
    def is_condition_met(self) -> bool:
        if (self.flag.val >> self.flag_num) & 0x1:
            return True
        else:
            return False
    
       
    