import struct
import pyaurum
import enum
from jsystem.typedchunk import *
from copy import deepcopy

__all__ = [
    # Classes
    "JPAKeyframe",
    "JPATexture",
    "JPAChunk",
    "JPADynamicsBlock",
    "JPAFieldBlock",
    "JPAKeyBlock",
    "JPABaseShape",
    "JPAExtraShape",
    "JPAChildShape",
    "JPAExTexShape",
    "JPAResource",
    "JParticlesContainer"
]


class JPATexture:
    def __init__(self):
        self.file_name = ""          # Texture file name
        self.bti_data = bytearray()  # BTI texture data
        self.total_size = 0          # Total size in bytes, set when (un)packing

    def unpack(self, buffer, offset: int = 0):
        self.total_size = pyaurum.get_s32(buffer, offset + 0x4)
        self.file_name = pyaurum.read_fixed_string(buffer, offset + 0xC, 0x14)
        self.bti_data = buffer[offset + 0x20:offset + self.total_size]

    def pack(self) -> bytes:
        # Pack name and align BTI data
        out_name = pyaurum.pack_fixed_string(self.file_name, 0x14)
        out_pad_bti = pyaurum.align32(self.bti_data)

        # Calculate total size; 0x20 = header and name size
        self.total_size = 0x20 + len(self.bti_data) + len(out_pad_bti)

        # Assemble output
        out_packed = bytearray(struct.pack(">3i", 0x54455831, self.total_size, 0))
        out_packed += out_name + self.bti_data + out_pad_bti

        return out_packed

    def replace_with(self, other):
        self.file_name = other.file_name
        self.bti_data = other.bti_data[:]

# Barebones chunk that will auto unpack and repack to json and bytes.
class JPAChunk:
    def __init__(self):
        self.auto_chunks = [] # Put a chunk in here to auto unpack, repack, etc.
    def unpack(self, buffer, offset: int = 0):
        for var in self.auto_chunks:
            var.unpack(buffer, offset)
            offset += var.get_size()
    def unpack_json(self, entry):
        for var in self.auto_chunks:
            var.unpack_json(entry)
    def pack(self) -> bytes:
        binary_data = bytearray()
        for var in self.auto_chunks:
            var_data = var.pack()
            if var_data is None:
                continue
            binary_data += var_data
        return binary_data
    def pack_json(self):
        obj = dict()
        for var in self.auto_chunks:
            var.pack_json(obj)
        return obj
    
# Standard chunk with a size, a magic, and debug info
class JPAStandardChunk:
    def __init__(self, magic):
        super().__init__()
        self.magic = magic
        self.binary_data = bytearray(0)
    def unpack(self, buffer, offset: int = 0):
        size = pyaurum.get_s32(buffer, offset + 0x4) - 8
        offset += 0x8
        self.binary_data = buffer[offset:offset + size]
        JPAChunk.unpack(self, buffer, offset)
    def unpack_json(self, entry):
        self.binary_data = bytes.fromhex(entry["BinaryDataDONOTEDIT"])
        for var in self.auto_chunks:
            var.unpack_json(entry)
    def pack(self) -> bytes:
        binary_data = JPAChunk.pack(self)
        self.identify_changes(binary_data)
        self.binary_data = binary_data
        out_data = binary_data + pyaurum.align4(binary_data)
        return self.magic.encode("ascii") + pyaurum.pack_s32(8 + len(out_data)) + out_data
    def pack_json(self):
        obj = dict()
        for var in self.auto_chunks:
            var.pack_json(obj)
        obj["BinaryDataDONOTEDIT"] = self.binary_data.hex()
        return obj
    
    def identify_changes(self, binary_data, set_binary_data=True):
        if (self.binary_data == None or binary_data == None):
            return
        if (self.binary_data != binary_data or not binary_data):
            print(type(self).__name__, "identified changes:")
            print("OLD", self.binary_data.hex())
            print("NEW", binary_data.hex())
            offset = 0
            for x in self.auto_chunks:
                size = x.get_size()
                if (offset + size > len(self.binary_data) or offset + size > len(binary_data)):
                    break
                y = deepcopy(x)
                y.unpack(self.binary_data, offset)
                new_obj = dict()
                x.pack_json(new_obj)
                old_obj = dict()
                y.pack_json(old_obj)
                old_bin = self.binary_data[offset:offset + size]
                new_bin = binary_data[offset:offset + size]
                if (new_bin != old_bin):
                    print(old_obj, "->", new_obj)
                    #print(old_bin, "->", new_bin, "size:", size)
                offset += size
            if set_binary_data:
                self.binary_data = binary_data

class JPAKeyframe(JPAChunk):
    def __init__(self):
        self.time = F32Chunk("Time", 0.0)
        self.value = F32Chunk("Value", 0.0)
        self.tan_in = F32Chunk("TangentIn", 0.0)
        self.tan_out = F32Chunk("TangentOut", 0.0)
        self.auto_chunks = [self.time, self.value, self.tan_in, self.tan_out]

class JPAColorFrame(JPAChunk):
    def __init__(self):
        self.frame = U16Chunk("Frame", 0)
        self.color = U32ChunkBytes("Color", bytes())
        self.auto_chunks = [self.frame, self.color]

class JPADynamicsBlock(JPAStandardChunk):
    def __init__(self):
        super().__init__("BEM1")
        self.flags = Flag32Chunk("Flags")
        self.flags.assign_flag("VolumeType", 8, 0x07, VolumeType, VolumeType.CUBE) # 8, 9, 10
        self.flags.assign_flag("FixedDensity", 0, 0x01, bool) # 0
        self.flags.assign_flag("FixedInterval", 1, 0x01, bool) # 1
        self.flags.assign_flag("InheritScale", 2, 0x01, bool) # 2
        self.flags.assign_flag("FollowEmitter", 3, 0x01, bool) # 3
        self.flags.assign_flag("FollowEmitterChild", 4, 0x01, bool) # 4

        self.unknown = U32ChunkBytes("Unknown")
        self.emitter_scale_x = F32Chunk("EmitterScaleX")
        self.emitter_scale_y = F32Chunk("EmitterScaleY")
        self.emitter_scale_z = F32Chunk("EmitterScaleZ")
        self.emitter_translation_x = F32Chunk("EmitterTranslationX")
        self.emitter_translation_y = F32Chunk("EmitterTranslationY")
        self.emitter_translation_z = F32Chunk("EmitterTranslationZ")
        self.emitter_direction_x = F32Chunk("EmitterDirectionX")
        self.emitter_direction_y = F32Chunk("EmitterDirectionY")
        self.emitter_direction_z = F32Chunk("EmitterDirectionZ")
        self.initial_velocity_omni = F32Chunk("InitialVelocityOmni")
        self.initial_velocity_axis = F32Chunk("InitialVelocityAxis")
        self.initial_velocity_random = F32Chunk("InitialVelocityRandom")
        self.initial_velocity_direction = F32Chunk("InitialVelocityDirection")
        self.spread = F32Chunk("Spread")
        self.initial_velocity_ratio = F32Chunk("InitialVelocityRatio")
        self.rate = F32Chunk("Rate")
        self.rate_random = F32Chunk("RateRandom")
        self.lifetime_random = F32Chunk("LifetimeRandom")
        self.volume_sweep = F32Chunk("VolumeSweep")
        self.volume_minimum_radius = F32Chunk("VolumeMinimumRadius")
        self.air_resistance = F32Chunk("AirResistance")
        self.moment_random = F32Chunk("MomentRandom")
        self.emitter_rotation_x_deg = U16Chunk("EmitterRotationXDeg")
        self.emitter_rotation_y_deg = U16Chunk("EmitterRotationYDeg")
        self.emitter_rotation_z_deg = U16Chunk("EmitterRotationZDeg")
        self.max_frame = U16Chunk("MaxFrame")
        self.start_frame = U16Chunk("StartFrame")
        self.lifetime = U16Chunk("Lifetime")
        self.volume_size = U16Chunk("VolumeSize")
        self.division_number = U16Chunk("DivisionNumber")
        self.rate_step = U8Chunk("RateStep")
        self.auto_chunks = [
            self.flags,self.unknown,
            self.emitter_scale_x, self.emitter_scale_y, self.emitter_scale_z,
            self.emitter_translation_x, self.emitter_translation_y, self.emitter_translation_z,
            self.emitter_direction_x, self.emitter_direction_y, self.emitter_direction_z,
            self.initial_velocity_omni, self.initial_velocity_axis, self.initial_velocity_random,
            self.initial_velocity_direction, self.spread, self.initial_velocity_ratio,
            self.rate, self.rate_random, self.lifetime_random, self.volume_sweep, 
            self.volume_minimum_radius, self.air_resistance, self.moment_random,
            self.emitter_rotation_x_deg, self.emitter_rotation_y_deg, self.emitter_rotation_z_deg,
            self.max_frame, self.start_frame, self.lifetime, self.volume_size, 
            self.division_number, self.rate_step, Offset(0x3)
        ]


class JPAFieldBlock(JPAStandardChunk):
    def __init__(self):
        super().__init__("FLD1")
        self.flags = Flag32Chunk("FieldFlags")
        self.flags.assign_flag("FieldType", 0, 0xF, FieldType) # 0, 1, 2, 3
        self.flags.assign_flag("VelocityType", 8, 0x03, FieldAddType) # 8, 9
        self.flags.assign_flag("NoInheritRotate", 17, 0x1, bool) # 17
        self.flags.assign_flag("AirDrag", 18, 0x1, bool) # 18
        self.flags.assign_flag("FadeUseEnterTime", 19, 0x1, bool) # 19
        self.flags.assign_flag("FadeUseDistanceTime", 20, 0x1, bool) # 20
        self.flags.assign_flag("FadeUseFadeIn", 21, 0x1, bool) # 21
        self.flags.assign_flag("FadeUseFadeOut", 22, 0x1, bool) # 22
        self.position_x = F32Chunk("PositionX")
        self.position_y = F32Chunk("PositionY")
        self.position_z = F32Chunk("PositionZ")
        self.direction_x = F32Chunk("DirectionX")
        self.direction_y = F32Chunk("DirectionY")
        self.direction_z = F32Chunk("DirectionZ")
        self.param_1 = F32Chunk("Param1")
        self.param_2 = F32Chunk("Param2")
        self.param_3 = F32Chunk("Param3")
        self.fade_in = F32Chunk("FadeIn")
        self.fade_out = F32Chunk("FadeOut")
        self.enter_time = F32Chunk("EnterTime")
        self.distance_time = F32Chunk("DistanceTime")
        self.cycle = U8Chunk("Cycle")
        self.auto_chunks = [
            self.flags, 
            self.position_x, self.position_y, self.position_z,
            self.direction_x, self.direction_y, self.direction_z,
            self.param_1, self.param_2, self.param_3,
            self.fade_in, self.fade_out,
            self.enter_time, self.distance_time,
            self.cycle, Offset(0x3)
        ]

class JPAKeyBlock(JPAStandardChunk):
    def __init__(self):
        super().__init__("KFA1")
        self.key_type = U8Chunk("KeyType") # KeyType enum
        self.key_count = U8Chunk("KeyCount")
        unused = U8Chunk("Unused")
        self.loop = BoolChunk("Loop")
        self.auto_chunks = [self.key_type, self.key_count, unused, self.loop]
        self.keyframes = []
    
    def unpack(self, buffer, offset: int = 0):
        size = pyaurum.get_s32(buffer, offset + 0x4) - 8
        offset += 0x8
        self.binary_data = buffer[offset:offset + size]
        for var in self.auto_chunks:
            var.unpack(buffer, offset)
            offset += var.get_size()
        for i in range(self.key_count.val):
            keyframe = JPAKeyframe()
            keyframe.unpack(buffer, offset + (0x10 * i))
            self.keyframes.append(keyframe)

    def unpack_json(self, entry):
        JPAStandardChunk.unpack_json(self, entry)
        self.keyframes = []
        for keyframe_json in entry["Keyframes"]:
            key = JPAKeyframe()
            key.unpack_json(keyframe_json)
            self.keyframes.append(key)

    def pack(self) -> bytes:
        self.key_count.val = len(self.keyframes)
        binary_data = JPAChunk.pack(self)
        for keyframe in self.keyframes:
            binary_data += keyframe.pack()
        self.identify_changes(binary_data)
        out_data = binary_data + pyaurum.align4(self.binary_data)
        return "KFA1".encode("ascii") + pyaurum.pack_s32(8 + len(out_data)) + out_data

    def pack_json(self):
        obj = dict()
        for var in self.auto_chunks:
            var.pack_json(obj)
        keyframes = []
        for keyframe in self.keyframes:
            keyframes.append(keyframe.pack_json())
        obj["Keyframes"] = keyframes
        obj["BinaryDataDONOTEDIT"] = self.binary_data.hex()
        return obj


class JPABaseShape(JPAStandardChunk):
    def __init__(self):
        super().__init__("BSP1")
        # Unknown flags: 11, 13, 23 
        # 19 (may be unused)
        self.flags = Flag32Chunk("BaseShapeFlags") # 0x8
        self.flags.assign_flag("ShapeType", 0, 0xF, ShapeType) # 0, 1, 2, 3
        self.flags.assign_flag("DirectionType", 4, 0x7, DirectionType) # 4, 5, 6
        self.flags.assign_flag("RotationType", 7, 0x7, RotationType) # 7, 8, 9
        self.flags.assign_flag("PlaneType", 10, 0x1, PlaneType) # 10
        self.flags.assign_flag("FlagsUnk11", 11, 0x1, bool)
        self.flags.assign_flag("IsGlobalColorAnimation", 12, 0x01, bool) # 12
        self.flags.assign_flag("FlagsUnk13", 13, 0x1, bool)
        self.flags.assign_flag("IsGlobalTextureAnimation", 14, 0x01, bool) # 14
        self.flags.assign_flag("ColorInSelect", 15, 0x7, int) # 15, 16, 17
        self.flags.assign_flag("AlphaInSelect", 18, 0x1, int) # 18
        # 19 is never set in SMG1 or SMG2.
        self.flags.assign_flag("IsEnableProjection",20, 0x01, bool) # 20
        self.flags.assign_flag("IsDrawForwardAhead", 21, 0x1, bool) # 21
        self.flags.assign_flag("IsDrawPrintAhead", 22, 0x1, bool) # 22
        self.flags.assign_flag("FlagsUnk23", 23, 0x1, bool)
        self.flags.assign_flag("IsEnableTexScrollAnim", 24, 0x1, bool) # 24
        self.flags.assign_flag("DoubleTilingS", 25, 0x1, bool) # 25
        self.flags.assign_flag("DoubleTilingT", 26, 0x1, bool) # 26
        self.flags.assign_flag("IsNoDrawParent", 27, 0x1, bool) # 27
        self.flags.assign_flag("IsNoDrawChild", 28, 0x1, bool) # 28 - never set
        # local primary_color_data_offset 0xC - 0xE
        # local environment_color_data_offset 0xE-0x10
        self.base_size_x = F32Chunk("BaseSizeX") # 0x10
        self.base_size_y = F32Chunk("BaseSizeY") # 0x14
        # Unknown: 10, 14
        self.blend_mode_flags = Flag16Chunk("BlendModeFlags") # 0x18
        self.blend_mode_flags.assign_flag("BlendMode", 0, 0x3, BlendMode), # 0, 1
        self.blend_mode_flags.assign_flag("SourceFactor", 2, 0xF, BlendFactor) # 2, 3, 4, 5
        self.blend_mode_flags.assign_flag("DestinationFactor", 6, 0xF, BlendFactor) # 6, 7, 8, 9
        self.blend_mode_flags.assign_flag("BlendModeFlagsUnk10", 10, 0x1, bool)
        self.blend_mode_flags.assign_flag("BlendModeFlagsUnk14", 14, 0x1, bool)
        self.alpha_compare_flags = Flag8Chunk("AlphaCompareFlags") # 0x1A
        self.alpha_compare_flags.assign_flag("AlphaCompareType0", 0, 0x7, CompareType) # 0, 1, 2
        self.alpha_compare_flags.assign_flag("AlphaOperator", 3, 0x03, AlphaOperator) # 3, 4
        self.alpha_compare_flags.assign_flag("AlphaCompareType1", 5, 0x7, CompareType) # 5, 6, 7
        self.alpha_reference_0 = U8Chunk("AlphaReference0") # 0x1B
        self.alpha_reference_1 = U8Chunk("AlphaReference1") # 0x1C
        # Unknown: 5
        self.z_mode_flags = Flag8Chunk("ZModeFlags") # 0x1D
        self.z_mode_flags.assign_flag("DepthTest", 0, 0x1, bool) # 0
        self.z_mode_flags.assign_flag("DepthCompareType", 1, 0x7, CompareType) # 1, 2, 3
        self.z_mode_flags.assign_flag("DepthWrite", 4, 0x1, bool) # 4
        self.z_mode_flags.assign_flag("ZModeFlagsUnk5", 5, 0x1, int) # 4
        # Unknown: 1
        self.texture_flags = Flag8Chunk("TextureFlags") # 0x1E
        self.texture_flags.assign_flag("IsEnableTexAnim", 0, 0x1, bool) # 0
        self.texture_flags.assign_flag("TexFlagsUnk1", 1, 0x1, bool)
        self.texture_flags.assign_flag("TexCalcIndexType", 2, 0x7, CalcIndexType) # 2, 3, 4
        # local texture_index_anim_count 0x1F-0x20
        self.texture_index = U8Chunk("TextureIndex") # 0x20
        # [0, 2]
        self.color_flags = Flag8Chunk("ColorFlags") # 0x21
        self.color_flags.assign_flag("ColorFlagsUnk0", 0, 0x1, bool)
        self.color_flags.assign_flag("IsPrimaryColorAnimEnabled", 1, 0x1, bool) # 1
        self.color_flags.assign_flag("ColorFlagsUnk2", 2, 0x1, bool)
        self.color_flags.assign_flag("IsEnvironmentColorAnimEnabled", 3, 0x1, bool), # 3
        self.color_flags.assign_flag("ColorCalcIndexType", 4, 0x7, CalcIndexType) # 4, 5, 6
        #self.primary_color_animation_data_count = U8Chunk("PrimaryColorAnimationDataCount", 0, 0x22) # 
        #self.environment_color_animation_data_count = U8Chunk("EnvironmentColorAnimationDataCount", 0, 0x23) #
        self.color_animation_max_frame = U16Chunk("ColorAnimationMaxFrame") # 0x24
        self.primary_color = U32ChunkBytes("PrimaryColor") # 0x26
        self.environment_color = U32ChunkBytes("EnvironmentColor") # 0x2A
        self.animation_random = U8Chunk("AnimationRandom") # 0x2E
        self.color_loop_offset_mask = U8Chunk("ColorLoopOffsetMask") # 0x2F
        self.texture_index_loop_offset_mask = U8Chunk("TextureIndexLoopOffsetMask") # 0x30

        self.tex_init_trans_x = FlagConditionalChunk(F32Chunk("TexInitTransX", 0.0), self.flags, 24)
        self.tex_init_trans_y = FlagConditionalChunk(F32Chunk("TexInitTransY", 0.0), self.flags, 24)
        self.tex_init_scale_x = FlagConditionalChunk(F32Chunk("TexInitScaleX", 1.0), self.flags, 24)
        self.tex_init_scale_y = FlagConditionalChunk(F32Chunk("TexInitScaleY", 1.0), self.flags, 24)
        self.tex_init_rot = FlagConditionalChunk(F32Chunk("TexInitRotation", 0.0), self.flags, 24)
        self.tex_inc_trans_x = FlagConditionalChunk(F32Chunk("TexIncTransX", 0.0), self.flags, 24)
        self.tex_inc_trans_y = FlagConditionalChunk(F32Chunk("TexIncTransY", 0.0), self.flags, 24)
        self.tex_inc_scale_x = FlagConditionalChunk(F32Chunk("TexIncScaleX", 1.0), self.flags, 24)
        self.tex_inc_scale_y = FlagConditionalChunk(F32Chunk("TexIncScaleY", 1.0), self.flags, 24)
        self.tex_inc_rot = FlagConditionalChunk(F32Chunk("TexIncRotation", 0.0), self.flags, 24)
        self.texture_index_anim_data = []
        self.primary_color_data = []
        self.environment_color_data = []
        # order DOES matter
        self.auto_chunks = [self.flags, Offset(0x4), self.base_size_x, self.base_size_y, self.blend_mode_flags, self.alpha_compare_flags, 
                                 self.alpha_reference_0, self.alpha_reference_1, 
                                 self.z_mode_flags, self.texture_flags, Offset(0x1), self.texture_index, 
                                 self.color_flags, Offset(0x2), self.color_animation_max_frame, self.primary_color, self.environment_color,
                                 self.animation_random, self.color_loop_offset_mask, self.texture_index_loop_offset_mask, Offset(0x3), self.tex_init_trans_x,
                                 self.tex_init_trans_y, self.tex_init_scale_x, self.tex_init_scale_y, self.tex_init_rot,
                                 self.tex_inc_trans_x, self.tex_inc_trans_y, self.tex_inc_scale_x, self.tex_inc_scale_y, self.tex_inc_rot]


    def unpack(self, buffer, offset: int = 0):
        rel_offset = 8 # this is the offset of the first var we auto unpack
        for var in self.auto_chunks:
            var.unpack(buffer, offset + rel_offset)
            rel_offset += var.get_size()
        initial_offset = offset
        size = pyaurum.get_s32(buffer, offset + 0x4) - 8
        self.extra_data = buffer[offset + 0x34:offset + size + 8]
        self.binary_data = buffer[offset + 0x8:offset + 0x8 + size]

        primary_color_data_offset = pyaurum.get_u16(buffer, offset + 0xC)
        environment_color_data_offset = pyaurum.get_u16(buffer, offset + 0xE)
        texture_index_anim_count = pyaurum.get_u8(buffer, offset + 0x1F)
        primary_color_animation_data_count = pyaurum.get_u8(buffer, offset + 0x22)
        environment_color_animation_data_count = pyaurum.get_u8(buffer, offset + 0x23)
        extra_data_offset = offset + 0x34


        if (bool((self.flags.get_val() >> 24) & 0x01)):
            extra_data_offset += 0x28

        self.texture_index_anim_data = []
        if self.texture_flags.get_val_flag_name("IsEnableTexAnim"):
            self.texture_index_anim_data = pyaurum.get_u8_array(buffer, extra_data_offset, texture_index_anim_count)

        self.primary_color_data = []
        if (self.color_flags.get_val_flag_name("IsPrimaryColorAnimEnabled")):
            primary_color_data_offset += initial_offset
            for i in range(primary_color_animation_data_count):
                frame = JPAColorFrame()
                current_offset = primary_color_data_offset + (i * 0x6)
                frame.unpack(buffer, current_offset)
                self.primary_color_data.append(frame)
        self.environment_color_data = []
        if (self.color_flags.get_val_flag_name("IsEnvironmentColorAnimEnabled")):
            environment_color_data_offset += initial_offset
            for i in range(environment_color_animation_data_count):
                frame = JPAColorFrame()
                current_offset = environment_color_data_offset + (i * 0x6)
                frame.unpack(buffer, current_offset)
                self.environment_color_data.append(frame)

    def unpack_json(self, entry):
        for var in self.auto_chunks:
            var.unpack_json(entry)
        self.binary_data = bytes.fromhex(entry["BinaryDataDONOTEDIT"])
        self.texture_index_anim_data = entry["TextureIndexAnimData"]
        self.primary_color_data = []
        for primary_key in entry["PrimaryColorKeyframes"]:
            primary_color = JPAColorFrame()
            primary_color.unpack_json(primary_key)
            self.primary_color_data.append(primary_color)
        self.environment_color_data = []
        for env_key in entry["EnvironmentColorKeyframes"]:
            environment_color = JPAColorFrame()
            environment_color.unpack_json(env_key)
            self.environment_color_data.append(environment_color)

    def pack(self) -> bytes:
        binary_data = bytearray()
        for var in self.auto_chunks:
            var_data = var.pack()
            if var_data is None:
                continue
            binary_data += var_data
        extra_data = bytes()
        extra_data_offset = 0x34
        if self.flags.get_val_flag_name("IsEnableTexScrollAnim"):
            extra_data_offset += 0x28
        if self.texture_flags.get_val_flag_name("IsEnableTexAnim"):
            extra_data += pyaurum.pack_u8_array(self.texture_index_anim_data)
            extra_data += pyaurum.align4(extra_data)
            binary_data[0x17:0x18] = pyaurum.pack_u8(len(self.texture_index_anim_data))
        if (self.color_flags.get_val_flag_name("IsPrimaryColorAnimEnabled")):
            offs = len(extra_data) + extra_data_offset
            for primary_color in self.primary_color_data:
                extra_data += primary_color.pack()
            extra_data += pyaurum.align4(extra_data)
            binary_data[0x4:0x6] = pyaurum.pack_u16(offs)
            binary_data[0x1A:0x1B] = pyaurum.pack_u8(len(self.primary_color_data))
        if (self.color_flags.get_val_flag_name("IsEnvironmentColorAnimEnabled")):
            offs = len(extra_data) + extra_data_offset
            for environment_color in self.environment_color_data:
                extra_data += environment_color.pack()
            extra_data += pyaurum.align4(extra_data)
            binary_data[0x6:0x8] = pyaurum.pack_u16(offs)
            binary_data[0x1B:0x1C] = pyaurum.pack_u8(len(self.environment_color_data))
        binary_data += extra_data
        self.identify_changes(binary_data)
        out_data = binary_data + pyaurum.align4(binary_data)
        return "BSP1".encode("ascii") + pyaurum.pack_s32(8 + len(out_data)) + out_data

    def pack_json(self):
        obj = dict()
        for var in self.auto_chunks:
            var.pack_json(obj)
        obj["BinaryDataDONOTEDIT"] = self.binary_data.hex()
        if self.texture_flags.get_val_flag_name("IsEnableTexAnim"):
            obj["TextureIndexAnimData"] = self.texture_index_anim_data
        else:
            obj["TextureIndexAnimData"] = []
        primary_color_keys = []
        if (self.color_flags.get_val_flag_name("IsPrimaryColorAnimEnabled")):
            for primary_color in self.primary_color_data:
                primary_color_keys.append(primary_color.pack_json())
        environment_color_keys = []
        if (self.color_flags.get_val_flag_name("IsEnvironmentColorAnimEnabled")):
            for environment_color in self.environment_color_data:
                environment_color_keys.append(environment_color.pack_json())
        obj["EnvironmentColorKeyframes"] = environment_color_keys
        obj["PrimaryColorKeyframes"] = primary_color_keys
        return obj


class JPAExtraShape(JPAStandardChunk):
    def __init__(self):
        super().__init__("ESP1")
        # Unknown set flags: 2, 3
        self.flags = Flag32Chunk("ExtraShapeFlags")
        self.flags.assign_flag("IsEnableScale", 0, 0x1, bool) # 0
        self.flags.assign_flag("IsDiffXY", 1, 0x1, bool) # 1
        # Note: Unk2 and Unk3 are either both set, or neither set.
        self.flags.assign_flag("FlagsUnk2", 2, 0x1, bool)
        self.flags.assign_flag("FlagsUnk3", 3, 0x1, bool)
        self.flags.assign_flag("ScaleAnimTypeX", 8, 0x03, CalcScaleAnimType) # 8, 9
        self.flags.assign_flag("ScaleAnimTypeY", 10, 0x03, CalcScaleAnimType) # 10, 11
        self.flags.assign_flag("PivotX", 12, 0x03, int) # 12, 13
        self.flags.assign_flag("PivotY", 14, 0x03, int) # 14, 15
        self.flags.assign_flag("IsEnableAlpha", 16, 0x1, bool) # 16
        self.flags.assign_flag("IsEnableSinWave", 17, 0x1, bool) # 17
        self.flags.assign_flag("IsEnableRotate", 24, 0x1, bool) # 24
        self.scale_in_timing = F32Chunk("ScaleInTiming")
        self.scale_out_timing = F32Chunk("ScaleOutTiming")
        self.scale_in_value_x = F32Chunk("ScaleInValueX")
        self.scale_out_value_x = F32Chunk("ScaleOutValueX")
        self.scale_in_value_y = F32Chunk("ScaleInValueY")
        self.scale_out_value_y = F32Chunk("ScaleOutValueY")
        self.scale_out_random = F32Chunk("ScaleOutRandom")
        self.scale_animation_x_max_frame = U16Chunk("ScaleAnimationXMaxFrame")
        self.scale_animation_y_max_frame = U16Chunk("ScaleAnimationYMaxFrame")
        self.alpha_in_timing = F32Chunk("AlphaInTiming")
        self.alpha_out_timing = F32Chunk("AlphaOutTiming")
        self.alpha_in_value = F32Chunk("AlphaInValue")
        self.alpha_base_value = F32Chunk("AlphaBaseValue")
        self.alpha_out_value = F32Chunk("AlphaOutValue")
        self.alpha_wave_frequency = F32Chunk("AlphaWaveFrequency")
        self.alpha_wave_random = F32Chunk("AlphaWaveRandom")
        self.alpha_wave_amplitude = F32Chunk("AlphaWaveAmplitude")
        self.rotate_angle = F32Chunk("RotateAngle")
        self.rotate_angle_random = F32Chunk("RotateAngleRandom")
        self.rotate_speed = F32Chunk("RotateSpeed")
        self.rotate_speed_random = F32Chunk("RotateSpeedRandom")
        self.rotate_direction = F32Chunk("RotateDirection")
        self.auto_chunks = [
            self.flags, self.scale_in_timing, self.scale_out_timing, self.scale_in_value_x, self.scale_out_value_x,
            self.scale_in_value_y, self.scale_out_value_y, self.scale_out_random,
            self.scale_animation_x_max_frame, self.scale_animation_y_max_frame,
            self.alpha_in_timing, self.alpha_out_timing, self.alpha_in_value, self.alpha_base_value,
            self.alpha_out_value, self.alpha_wave_frequency, self.alpha_wave_random, self.alpha_wave_amplitude,
            self.rotate_angle, self.rotate_angle_random, self.rotate_speed, self.rotate_speed_random,
            self.rotate_direction
        ]


class JPAChildShape(JPAStandardChunk):
    def __init__(self):
        super().__init__("SSP1")
        # Unknown but set: 19, 20
        self.flags = Flag32Chunk("Flags")
        self.flags.assign_flag("ShapeType", 0, 0xF, ShapeType) # 0, 1, 2, 3
        self.flags.assign_flag("DirectionType", 4, 0x7, DirectionType) # 4, 5, 6
        self.flags.assign_flag("RotationType", 7, 0x7, RotationType) # 7, 8, 9
        self.flags.assign_flag("PlaneType", 10, 0x1, PlaneType) # 10
        self.flags.assign_flag("IsInheritedScale", 16, 0x01, bool) # 16
        self.flags.assign_flag("IsInheritedAlpha", 17, 0x01, bool) # 17
        self.flags.assign_flag("IsInheritedRGB", 18, 0x01, bool) # 18
        self.flags.assign_flag("FlagsUnk19", 19, 0x01, bool)
        self.flags.assign_flag("FlagsUnk20", 20, 0x01, bool)
        self.flags.assign_flag("IsEnableField", 21, 0x01, bool) # 21
        self.flags.assign_flag("IsEnableScaleOut", 22, 0x01, bool) # 22
        self.flags.assign_flag("IsEnableAlphaOut", 23, 0x01, bool) # 23
        self.flags.assign_flag("IsEnableRotate", 24, 0x01, bool) # 24
        self.position_random = F32Chunk("PositionRandom")
        self.base_velocity = F32Chunk("BaseVelocity")
        self.base_velocity_random = F32Chunk("BaseVelocityRandom")
        self.velocity_influence_rate = F32Chunk("VelocityInfluenceRate")
        self.gravity = F32Chunk("Gravity")
        self.global_scale_2d_x = F32Chunk("GlobalScale2DX")
        self.global_scale_2d_y = F32Chunk("GlobalScale2DY")
        self.inherit_scale = F32Chunk("InheritScale")
        self.inherit_alpha = F32Chunk("InheritAlpha")
        self.inherit_rgb = F32Chunk("InheritRGB")
        self.primary_color = U32ChunkBytes("PrimaryColor")
        self.environment_color = U32ChunkBytes("EnvironmentColor")
        self.timing = F32Chunk("Timing")
        # my.self.life = SMGModdingChunk("Life")
        self.life = U16Chunk("Life")
        self.rate = U16Chunk("Rate")
        self.step = U8Chunk("Step")
        self.texture_index = U8Chunk("TextureIndex")
        self.rotate_speed = U16Chunk("RotateSpeed")

        self.auto_chunks = [
            self.flags, self.position_random, self.base_velocity, self.base_velocity_random,
            self.velocity_influence_rate, self.gravity, self.global_scale_2d_x, self.global_scale_2d_y,
            self.inherit_scale, self.inherit_alpha, self.inherit_rgb, self.primary_color,
            self.environment_color, self.timing, self.life, self.rate, self.step, 
            self.texture_index, self.rotate_speed
        ]

class JPAExTexShape(JPAStandardChunk):
    def __init__(self):
        super().__init__("ETX1")
        # Only 2 bits are set. That's crazy.
        self.flags = Flag32Chunk("ExTexFlags")
        self.flags.assign_flag("IndirectTextureMode", 0, 0x1, IndirectTextureMode)
        self.flags.assign_flag("UseSecondTextureIndex", 8, 0x1, bool)
        self.indirect_texture_matrix_0_0 = F32Chunk("IndirectTextureMatrix[0][0]")
        self.indirect_texture_matrix_0_1 = F32Chunk("IndirectTextureMatrix[0][1]")
        self.indirect_texture_matrix_0_2 = F32Chunk("IndirectTextureMatrix[0][2]")
        self.indirect_texture_matrix_1_0 = F32Chunk("IndirectTextureMatrix[1][0]")
        self.indirect_texture_matrix_1_1 = F32Chunk("IndirectTextureMatrix[1][1]")
        self.indirect_texture_matrix_1_2 = F32Chunk("IndirectTextureMatrix[1][2]")
        self.matrix_scale = S8Chunk("MatrixScale")
        self.indirect_texture_index = U8Chunk("IndirectTextureIndex")
        self.second_texture_index = U8Chunk("SecondTextureIndex")
        self.auto_chunks = [
            self.flags,
            self.indirect_texture_matrix_0_0, self.indirect_texture_matrix_0_1, self.indirect_texture_matrix_0_2,
            self.indirect_texture_matrix_1_0, self.indirect_texture_matrix_1_1, self.indirect_texture_matrix_1_2,
            self.matrix_scale, self.indirect_texture_index, self.second_texture_index, Offset(0x1)
        ]


class JPAResource:
    def __init__(self):
        self.name = None
        self.dynamics_block = JPADynamicsBlock() # JPADynamicsBlock
        self.field_blocks = list()               # list of JPAFieldBlock
        self.key_blocks = list()                 # list of JPAKeyBlock
        self.base_shape = JPABaseShape()         # JPABaseShape
        self.extra_shape = None                  # JPAExtraShape
        self.child_shape = None                  # JPAChildShape
        self.ex_tex_shape = None                 # JPAExTexShape
        self.texture_ids = list()                # List of texture IDs
        self.texture_names = list()              # List of texture file names, will be populated later on

        self.index = 0                           # The particles index inside the container
        self.total_size = 0                      # Total size in bytes, set when (un)packing

    def unpack(self, buffer, offset: int = 0):
        # Setup members
        self.name = None
        self.dynamics_block = None
        self.field_blocks.clear()
        self.key_blocks.clear()
        self.base_shape = None
        self.extra_shape = None
        self.child_shape = None
        self.ex_tex_shape = None
        self.texture_ids.clear()
        self.texture_names.clear()
        self.total_size = 8  # In SMG, the first 8 bytes are the header for JPAResource

        # Parse header
        self.index, num_sections, num_field_blocks, num_key_blocks, num_textures = struct.unpack_from(">2h3B", buffer, offset)
        offset += self.total_size

        # Go through all available sections
        for i in range(num_sections):
            # Parse block header and extract block
            magic = buffer[offset:offset + 0x4].decode("ascii")
            size = pyaurum.get_s32(buffer, offset + 0x4)
            block = buffer[offset:offset + size]

            # Parse JPADynamicsBlock
            if magic == "BEM1":
                self.dynamics_block = JPADynamicsBlock()
                self.dynamics_block.unpack(buffer, offset)
            # Parse JPAFieldBlock entries
            elif magic == "FLD1":
                field_block = JPAFieldBlock()
                field_block.unpack(buffer, offset)
                self.field_blocks.append(field_block)
            # Parse JPAKeyBlock entries
            elif magic == "KFA1":
                key_block = JPAKeyBlock()
                key_block.unpack(buffer, offset)
                self.key_blocks.append(key_block)
            # Parse JPABaseShape
            elif magic == "BSP1":
                self.base_shape = JPABaseShape()
                self.base_shape.unpack(buffer, offset)
            # Parse JPAExtraShape
            elif magic == "ESP1":
                self.extra_shape = JPAExtraShape()
                self.extra_shape.unpack(buffer, offset)
            # Parse JPAChildShape
            elif magic == "SSP1":
                self.child_shape = JPAChildShape()
                self.child_shape.unpack(buffer, offset)
            # Parse JPAExTexShape
            elif magic == "ETX1":
                self.ex_tex_shape = JPAExTexShape()
                self.ex_tex_shape.unpack(buffer, offset)
            # Parse texture ID database
            elif magic == "TDB1":
                for j in range(num_textures):
                    self.texture_ids.append(pyaurum.get_s16(block, 0x8 + j * 0x2))
            # Just to be sure we find a wrong section
            else:
                raise Exception(f"Unknown section {magic}")

            # Adjust offset and total size
            self.total_size += size
            offset += size

        if num_key_blocks != len(self.key_blocks):
            raise Exception(f"Expected {num_key_blocks} key blocks, found {len(self.key_blocks)}")
        if num_field_blocks != len(self.field_blocks):
            raise Exception(f"Expected {num_field_blocks} field blocks, found {len(self.field_blocks)}")

    def unpack_json(self, entry: dict):
        self.field_blocks.clear()
        self.key_blocks.clear()

        self.texture_ids.clear()
        self.texture_names = entry["textures"]

        self.index = -1
        self.total_size = 0

        if "dynamicsBlock" in entry:
            self.dynamics_block = JPADynamicsBlock()
            self.dynamics_block.unpack_json(entry["dynamicsBlock"])
        if "fieldBlocks" in entry:
            for field_block_json in entry["fieldBlocks"]:
                field_block = JPAFieldBlock()
                field_block.unpack_json(field_block_json)
                self.field_blocks.append(field_block)
        if "keyBlocks" in entry:
            for key_block_json in entry["keyBlocks"]:
                key_block = JPAKeyBlock()
                key_block.unpack_json(key_block_json)
                self.key_blocks.append(key_block)
        if "baseShape" in entry:
            self.base_shape = JPABaseShape()
            self.base_shape.unpack_json(entry["baseShape"])
        if "extraShape" in entry:
            self.extra_shape = JPAExtraShape()
            self.extra_shape.unpack_json(entry["extraShape"])
        if "childShape" in entry:
            self.child_shape = JPAChildShape()
            self.child_shape.unpack_json(entry["childShape"])
        if "exTexShape" in entry:
            self.ex_tex_shape = JPAExTexShape()
            self.ex_tex_shape.unpack_json(entry["exTexShape"])

    def pack(self) -> bytes:
        # Pack header
        num_field_blocks = len(self.field_blocks)
        num_key_blocks = len(self.key_blocks)
        num_textures = len(self.texture_ids)
        out_buf = bytearray() + struct.pack(">2h4B", self.index, 0, num_field_blocks, num_key_blocks, num_textures, 0)

        # Pack blocks
        num_sections = 1

        if self.dynamics_block:
            out_buf += self.dynamics_block.pack()
            num_sections += 1
        if len(self.field_blocks) > 0:
            for field_block in self.field_blocks:
                out_buf += field_block.pack()
                num_sections += 1
        if len(self.key_blocks) > 0:
            for key_block in self.key_blocks:
                out_buf += key_block.pack()
                num_sections += 1
        if self.base_shape:
            out_buf += self.base_shape.pack()
            num_sections += 1
        if self.extra_shape:
            out_buf += self.extra_shape.pack()
            num_sections += 1
        if self.child_shape:
            out_buf += self.child_shape.pack()
            num_sections += 1
        if self.ex_tex_shape:
            out_buf += self.ex_tex_shape.pack()
            num_sections += 1

        # Write section count
        struct.pack_into(">h", out_buf, 0x2, num_sections)

        # Pack texture ID database
        out_tdb1 = bytearray()

        for texture_id in self.texture_ids:
            out_tdb1 += pyaurum.pack_s16(texture_id)
        out_tdb1 += pyaurum.align4(out_tdb1, "\0")

        out_tdb1 = "TDB1".encode("ascii") + pyaurum.pack_s32(len(out_tdb1) + 8) + out_tdb1

        # Assemble output
        out_buf += out_tdb1
        self.total_size = len(out_buf)

        return out_buf

    def pack_json(self) -> dict:
        entry = dict()

        # Pack blocks
        if self.dynamics_block:
            entry["dynamicsBlock"] = self.dynamics_block.pack_json()
        if len(self.field_blocks) > 0:
            entry["fieldBlocks"] = list()

            for field_block in self.field_blocks:
                entry["fieldBlocks"].append(field_block.pack_json())
        if len(self.key_blocks) > 0:
            entry["keyBlocks"] = list()

            for key_block in self.key_blocks:
                entry["keyBlocks"].append(key_block.pack_json())
        if self.base_shape:
            entry["baseShape"] = self.base_shape.pack_json()
        if self.extra_shape:
            entry["extraShape"] = self.extra_shape.pack_json()
        if self.child_shape:
            entry["childShape"] = self.child_shape.pack_json()
        if self.ex_tex_shape:
            entry["exTexShape"] = self.ex_tex_shape.pack_json()

        # Pack texture names
        entry["textures"] = self.texture_names

        return entry

    def replace_with(self, other):
        self.name = other.name
        self.field_blocks.clear()
        self.key_blocks.clear()
        self.texture_names.clear()
        self.texture_names += other.texture_names

        self.dynamics_block = deepcopy(other.dynamics_block)

        for block in other.field_blocks:
            self.field_blocks.append(deepcopy(block))

        for block in other.key_blocks:
            self.key_blocks.append(deepcopy(block))

        self.base_shape = deepcopy(other.base_shape)
        self.extra_shape = deepcopy(other.extra_shape)
        self.child_shape = deepcopy(other.child_shape)
        self.ex_tex_shape = deepcopy(other.ex_tex_shape)


class JParticlesContainer:
    def __init__(self):
        self.particles = list()  # List of JPAResource entries
        self.textures = dict()   # JPATextures indexed by their file name

    def unpack(self, buffer, offset: int = 0):
        self.particles.clear()
        self.textures.clear()

        # Parse header
        if pyaurum.get_magic8(buffer, offset) != "JPAC2-10":
            raise Exception("Fatal! No JPAC2-10 data provided.")

        num_particles, num_textures, off_textures = struct.unpack_from(">HHI", buffer, offset + 0x8)

        # Parse JPATexture entries
        # We parse them first as we need the texture filenames for particles. This saves loading time as we do not have
        # to go through all the particles twice. However, in the actual JPC file, the particle data comes first.
        texture_filenames = list()
        next_offset = offset + off_textures

        for i in range(num_textures):
            texture = JPATexture()
            texture.unpack(buffer, next_offset)

            texture_filenames.append(texture.file_name)
            self.textures[texture.file_name] = texture
            next_offset += texture.total_size

        # Parse JPAResource entries
        next_offset = offset + 0x10

        for i in range(num_particles):
            particle = JPAResource()
            particle.unpack(buffer, next_offset)

            # Append texture file names for every particle
            for texture_index in particle.texture_ids:
                particle.texture_names.append(texture_filenames[texture_index])

            self.particles.append(particle)
            next_offset += particle.total_size

    def pack(self):
        # Pack header, we will write the textures offset later
        out_buf = bytearray() + pyaurum.pack_magic8("JPAC2-10")
        out_buf += struct.pack(">HHI", len(self.particles), len(self.textures), 0)

        # Pack JPAResource entries
        texture_name_to_id = list(self.textures.keys())

        for particle in self.particles:
            # Get texture IDs from texture names
            particle.texture_ids.clear()

            for texture_name in particle.texture_names:
                # This error can only occur in batch mode since the editor prevents saving if the error check finds
                # invalid texture names.
                try:
                    particle.texture_ids.append(texture_name_to_id.index(texture_name))
                except ValueError:
                    pass

            out_buf += particle.pack()

        # Align buffer and write offset to textures
        out_buf += pyaurum.align32(out_buf)
        struct.pack_into(">I", out_buf, 0xC, len(out_buf))

        # Pack JPATexture entries
        for texture in self.textures.values():
            out_buf += texture.pack()
        # No padding necessary here since textures are already aligned to 32 bytes

        # Return packed data
        return out_buf

class VolumeType(enum.IntEnum):
    CUBE = 0x00
    SPHERE = 0x01
    CYLINDER = 0x02
    TORUS = 0x03
    POINT = 0x04
    CIRCLE = 0x05
    LINE = 0x06

class FieldType(enum.IntEnum):
    GRAVITY = 0x00
    AIR = 0x01
    MAGNET = 0x02
    NEWTON = 0x03
    VORTEX = 0x04
    RANDOM = 0x05
    DRAG = 0x06
    CONVECTION = 0x07
    SPIN = 0x08

class FieldAddType(enum.IntEnum):
    FIELD_ACCEL = 0x00
    BASE_VELOCITY = 0x01
    FIELD_VELOCITY = 0x02

class KeyType(enum.IntEnum):
    RATE = 0x00
    VOLUME_SIZE = 0x01
    VOLUME_SWEEP = 0x02
    VOLUME_MIN_RADIUS = 0x03
    LIFETIME = 0x04
    MOMENT = 0x05
    INIT_VELO_OMNI = 0x06
    INIT_VELO_AXIS = 0x07
    INIT_VELO_DIRECTION = 0x08
    SPREAD = 0x09
    SCALE = 0x0A

class DirectionType(enum.IntEnum):
    VELOCITY = 0x00
    POSITION = 0x01
    POSITION_INVERSE = 0x02
    EMITTER_DIRECTION = 0x03
    PREVIOUS_PARTICLE = 0x04
    DIR_5 = 0x05

class RotationType(enum.IntEnum):
    Y = 0x00
    X = 0x01
    Z = 0x02
    XYZ = 0x03
    Y_JIGGLE = 0x04

class PlaneType(enum.IntEnum):
    XY = 0x00
    XZ = 0x01
    # X = 0x02 - there would need to be more than 1 bit for this to do anything

class ShapeType(enum.IntEnum):
    POINT = 0x00
    LINE = 0x01
    BILLBOARD = 0x02
    DIRECTION = 0x03
    DIRECTION_CROSS = 0x04
    STRIPE = 0x05
    STRIPE_CROSS = 0x06
    ROTATION = 0x07
    ROTATION_CROSS = 0x08
    DIRECTION_BILLBOARD = 0x09
    Y_BILLBOARD = 0x0A

class BlendMode(enum.IntEnum):
    NONE = 0
    BLEND = 1
    LOGIC = 2

class BlendFactor(enum.IntEnum):
    ZERO = 0
    ONE = 1
    SOURCE_COLOR = 2
    INVERSE_SOURCE_COLOR = 3
    SOURCE_COLOR_EXTRA = 4 # TODO figure out why two numbers are mapped to the same thing
    INVERSE_SOURCE_COLOR_EXTRA = 5 # TODO ^
    SOURCE_ALPHA = 6
    INVERSE_SOURCE_ALPHA = 7
    DESTINATION_ALPHA = 8
    INVERSE_DESTINATION_ALPHA = 9

class CompareType(enum.IntEnum):
    NEVER = 0
    LESS_THAN = 1
    LESS_THAN_EQUAL = 2
    EQUAL = 3
    NOT_EQUAL = 4
    GREATER_THAN_EQUAL = 5
    GREATER_THAN = 6
    ALWAYS = 7

class IndirectTextureMode(enum.IntEnum):
    OFF = 0
    NORMAL = 1

class AlphaOperator(enum.IntEnum):
    AND = 0
    OR = 1
    XOR = 2
    XNOR = 3

class CalcIndexType(enum.IntEnum):
    NORMAL = 0
    REPEAT = 1
    REVERSE = 2
    MERGE = 3
    RANDOM = 4

class CalcScaleAnimType(enum.IntEnum):
    NORMAL = 0
    REPEAT = 1
    REVERSE = 2