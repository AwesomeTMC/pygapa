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
    def set_val(self, new_val):
        self.val = new_val
    
class U8Chunk(TypedChunk):
    def __init__(self, name, default_val=0):
        super().__init__(name, default_val)
        self.size = 1
    def unpack(self, buffer, offset: int = 0):
        self.val = pyaurum.get_u8(buffer, offset)
    def pack(self) -> bytes:
        return pyaurum.pack_u8(self.val)
    def unpack_json(self, entry):
        self.val = entry[self.name]
    def set_val(self, new_val):
        if (self.val > 255):
            self.val = 255
        elif (self.val < 0):
            self.val = 0
        else:
            self.val = new_val

class S8Chunk(TypedChunk):
    def __init__(self, name, default_val=0):
        super().__init__(name, default_val)
        self.size = 1
    def unpack(self, buffer, offset: int = 0):
        self.val = pyaurum.get_s8(buffer, offset)
    def pack(self) -> bytes:
        return pyaurum.pack_s8(self.val)
    def unpack_json(self, entry):
        self.val = entry[self.name]
    def set_val(self, new_val):
        if (self.val > 127):
            self.val = 127
        elif (self.val < -127):
            self.val = -127
        else:
            self.val = new_val
        

class U16Chunk(TypedChunk):
    def __init__(self, name, default_val=0):
        super().__init__(name, default_val)
        self.size = 2
    def unpack(self, buffer, offset: int = 0):
        self.val = pyaurum.get_u16(buffer, offset)
    def pack(self) -> bytes:
        return pyaurum.pack_u16(self.val)
    def unpack_json(self, entry):
        self.val = entry[self.name]
    def set_val(self, new_val):
        if (self.val > 65535):
            self.val = 65535
        elif (self.val < 0):
            self.val = 0
        else:
            self.val = new_val
        

class U32Chunk(TypedChunk):
    def __init__(self, name, default_val=0):
        super().__init__(name, default_val)
        self.size = 4
    def unpack(self, buffer, offset: int = 0):
        self.val = pyaurum.get_u32(buffer, offset)
    def pack(self) -> bytes:
        return pyaurum.pack_u32(self.val)
    def unpack_json(self, entry):
        self.val = entry[self.name]
    def set_val(self, new_val):
        if (self.val > 4294967295):
            self.val = 4294967295
        elif (self.val < 0):
            self.val = 0
        else:
            self.val = new_val
        

class U32ChunkBytes(TypedChunk):
    def __init__(self, name, default_val=0):
        super().__init__(name, default_val)
        self.size = 4
    def unpack(self, buffer, offset: int = 0):
        self.val = buffer[offset:offset + 4]
    def pack(self) -> bytes:
        return self.val
    def pack_json(self, obj: dict):
        obj[self.name] = self.val.hex()
    def unpack_json(self, entry):
        self.val = bytes.fromhex(entry[self.name])
        

class F32Chunk(TypedChunk):
    def __init__(self, name, default_val=0):
        super().__init__(name, default_val)
        self.size = 4
    def unpack(self, buffer, offset: int = 0):
        self.val = pyaurum.get_f32(buffer, offset)
    def pack(self) -> bytes:
        return pyaurum.pack_f32(self.val)
    def unpack_json(self, entry):
        self.val = entry[self.name]
        
class BoolChunk(TypedChunk):
    def __init__(self, name, default_val=False):
        super().__init__(name, default_val)
        self.size = 1
    def unpack(self, buffer, offset: int = 0):
        self.val = pyaurum.get_bool(buffer, offset)
    def pack(self) -> bytes:
        ret = pyaurum.pack_bool(self.val)
        return ret
    def unpack_json(self, entry):
        self.val = entry[self.name] 

# offsets are necessary for the dynamic way chunks are unpacked and repacked
class Offset(TypedChunk):
    def __init__(self, size):
        self.size = size
        self.val = None
        self.name = "Offset"
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
        if (self.is_condition_met()):
            return self.chunk.get_size()
        return 0
    def get_val(self):
        return self.chunk.get_val()
    def set_val(self, new_val):
        return self.chunk.set_val(new_val)
    
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

class Flag():
    def __init__(self, name, right_shift, mask, flag_type):
        self.name = name
        self.right_shift = right_shift
        self.mask = mask
        self.flag_type = flag_type
# abstract, meant to be used in multi inheritance
class FlagChunk():
    def __init__(self) -> None:
        self.assigned_flags = []
    def pack_json(self, obj: dict):
        for flag in self.assigned_flags:
            val = self.get_val_flag(flag)
            obj[flag.name] = val
    def unpack_json(self, entry):
        self.val = 0
        for flag in self.assigned_flags:
            val = entry[flag.name]
            self.set_val_flag(flag, val)
    def set_val_flag_name(self, flag_name, val):
        flag = self.get_flag(flag_name)
        if not flag:
            raise NameError("Could not find flag with name", flag_name)
        self.set_val_flag(flag, val)
    def set_val_flag(self, flag, val):
        val = int(val)
        self.set_val(set_flag(self.get_val(), flag.right_shift, flag.mask, int(val)))
    def get_val_flag_name(self, flag_name: str):
        flag = self.get_flag(flag_name)
        if not flag:
            raise NameError("Could not find flag with name", flag_name)
        return self.get_val_flag(flag)
    def get_val_flag(self, flag: Flag):
        val = flag.flag_type(get_flag_int(self.get_val(), flag.right_shift, flag.mask))
        return val
    def assign_flag(self, name, right_shift, mask, flag_type, default_val=0):
        flag = Flag(name, right_shift, mask, flag_type)
        self.assigned_flags.append(flag)
        if int(default_val) != 0:
            self.set_val_flag(flag, default_val)
    def get_flag(self, name) -> Flag:
        for flag in self.assigned_flags:
            if (flag.name == name):
                return flag
        return None
class Flag32Chunk(FlagChunk,U32Chunk):
    def __init__(self, name, default_val=0):
        FlagChunk.__init__(self)
        U32Chunk.__init__(self,name,default_val)
class Flag16Chunk(FlagChunk,U16Chunk):
    def __init__(self, name, default_val=0):
        FlagChunk.__init__(self)
        U16Chunk.__init__(self,name,default_val)
class Flag8Chunk(FlagChunk,U8Chunk):
    def __init__(self, name, default_val=0):
        FlagChunk.__init__(self)
        U8Chunk.__init__(self,name,default_val)
def get_flag_int(var, right_shift, mask):
    return var >> right_shift & mask
# set a flag to a value no matter what was in it before.
# returns the result
def set_flag(var, left_shift, mask, val):
    result = var & ~(mask << left_shift)
    result |= (val << left_shift)
    return result
