import argparse
import copy
import enum
import jsystem
import mrformats
import os
import pyaurum
import sys

from PyQt5 import uic, QtGui, QtCore, QtWidgets

# General application info
APP_NAME = "pygapa"
APP_VERSION = "v0.7.3U"
APP_CREATOR = "Aurum, AwesomeTMC"
APP_TITLE = f"{APP_NAME} {APP_VERSION} -- by {APP_CREATOR}"

# Setup QT application
PROGRAM = QtWidgets.QApplication([])
ICON = QtGui.QIcon()
ICON.addFile("ui/icon.png", QtCore.QSize(32, 32))
PROGRAM.setWindowIcon(ICON)

# Setup exception hook
old_excepthook = sys.excepthook


def exception_hook(exctype, value, traceback):
    print(exctype, value, traceback)
    old_excepthook(exctype, value, traceback)
    sys.exit(1)


sys.excepthook = exception_hook

# ----------------------------------------------------------------------------------------------------------------------
# Load and fetch preferences
# ----------------------------------------------------------------------------------------------------------------------
__SETTINGS = QtCore.QSettings("pygapa.ini", QtCore.QSettings.IniFormat)


def get_localization() -> str:
    return __SETTINGS.value("localization", "en_us", str)


def set_localization(val: str):
    __SETTINGS.setValue("localization", val)


def get_last_file() -> str:
    return __SETTINGS.value("last_file", "", str)


def set_last_file(val: str):
    __SETTINGS.setValue("last_file", val)


def is_compress_arc():
    return __SETTINGS.value("compress_arc", True, bool)


def set_compress_arc(val: bool):
    __SETTINGS.setValue("compress_arc", val)


def get_wszst_rate() -> str:
    return __SETTINGS.value("wszst_rate", "ULTRA", str)


def set_wszst_rate(val: str):
    __SETTINGS.setValue("wszst_rate", val)


class StatusColor(enum.IntEnum):
    INFO = 0
    WARN = 1
    ERROR = 2


class PgpPreferencesWindow(QtWidgets.QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowFlag(QtCore.Qt.MSWindowsFixedSizeDialogHint, True)
        self.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        self.ui = uic.loadUi("ui/preferences.ui", self)

        self.checkCompressArc.stateChanged.connect(lambda state: set_compress_arc(state == 2))
        self.txtWszstRate.textEdited.connect(set_wszst_rate)

    def show(self):
        super().show()
        self.checkCompressArc.setChecked(is_compress_arc())
        self.txtWszstRate.setText(get_wszst_rate())


class PgpEditorMode(enum.IntEnum):
    EFFECT = 0
    PARTICLE = 1
    TEXTURE = 2
    DYNAMICS_BLOCK = 3
    FIELD_BLOCKS = 4
    FIELD_BLOCK = 5
    KEY_BLOCKS = 6
    KEY_BLOCK = 7
    BASE_SHAPE = 8
    EXTRA_SHAPE = 9
    CHILD_SHAPE = 10
    EX_TEX_SHAPE = 11


PBNODE_MODE = 1000
PBNODE_DATA = 1001


def create_data_node(text: str, mode: PgpEditorMode, data):
    node = QtWidgets.QTreeWidgetItem([text])
    node.setData(0, PBNODE_MODE, mode)
    node.setData(0, PBNODE_DATA, data)
    return node


class PgpEditor(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = uic.loadUi("ui/main.ui", self)
        self.setWindowTitle(APP_TITLE)

        # Particle data holders
        self.particle_data = None
        self.effect_arc = None
        self.particle_data_file = None
        self.current_effect = None
        self.copied_effect = None
        self.current_particle = None
        self.copied_particle = None
        self.current_texture = None

        # Populate drawing orders
        for draw_order in mrformats.PARTICLE_DRAW_ORDERS:
            self.comboEffectDrawOrder.addItem(draw_order)

        # File menu actions
        self.actionExit.triggered.connect(lambda: PROGRAM.exit())
        self.actionOpen.triggered.connect(self.open_particle_data)
        self.actionSave.triggered.connect(self.save_particle_data)
        self.actionSaveAs.triggered.connect(self.save_as_particle_data)

        # Register effect editing actions
        self.listEffects.itemSelectionChanged.connect(self.select_effect)

        self.actionToolAdd.triggered.connect(self.add_effect)
        self.actionToolDelete.triggered.connect(self.delete_effects)
        self.actionToolClone.triggered.connect(self.clone_effects)
        self.actionToolCopy.triggered.connect(self.copy_effect)
        self.actionToolReplace.triggered.connect(self.replace_effect)
        self.actionToolExport.triggered.connect(self.export_effects)
        self.actionToolImport.triggered.connect(self.import_effects)

        self.textEffectGroupName.textEdited.connect(self.set_effect_group_name)
        self.textEffectUniqueName.textEdited.connect(self.set_effect_unique_name)
        self.textEffectParentName.textEdited.connect(self.set_effect_parent_name)
        self.textEffectEffectName.textChanged.connect(self.set_effect_effect_name)
        self.textEffectJointName.textEdited.connect(self.set_effect_joint_name)
        self.textEffectAnimName.textChanged.connect(self.set_effect_anim_name)
        self.checkEffectContinueAnimEnd.stateChanged.connect(lambda s: self.set_effect_continue_anim_end(s == 2))
        self.spinnerEffectStartFrame.valueChanged.connect(self.set_effect_start_frame)
        self.spinnerEffectEndFrame.valueChanged.connect(self.set_effect_end_frame)
        self.spinnerEffectOffsetX.valueChanged.connect(self.set_effect_offset_x)
        self.spinnerEffectOffsetY.valueChanged.connect(self.set_effect_offset_y)
        self.spinnerEffectOffsetZ.valueChanged.connect(self.set_effect_offset_z)
        self.checkEffectAffectT.stateChanged.connect(lambda s: self.set_effect_affect_flag(s == 2, "T"))
        self.checkEffectAffectR.stateChanged.connect(lambda s: self.set_effect_affect_flag(s == 2, "R"))
        self.checkEffectAffectS.stateChanged.connect(lambda s: self.set_effect_affect_flag(s == 2, "S"))
        self.checkEffectFollowT.stateChanged.connect(lambda s: self.set_effect_follow_flag(s == 2, "T"))
        self.checkEffectFollowR.stateChanged.connect(lambda s: self.set_effect_follow_flag(s == 2, "R"))
        self.checkEffectFollowS.stateChanged.connect(lambda s: self.set_effect_follow_flag(s == 2, "S"))
        self.spinnerEffectScaleValue.valueChanged.connect(self.set_effect_scale_value)
        self.spinnerEffectRateValue.valueChanged.connect(self.set_effect_rate_value)
        self.spinnerEffectLightAffectValue.valueChanged.connect(self.set_effect_light_affect_value)
        self.textEffectPrmColor.textEdited.connect(self.set_effect_prm_color)
        self.textEffectEnvColor.textEdited.connect(self.set_effect_env_color)
        self.comboEffectDrawOrder.currentIndexChanged.connect(self.set_effect_draw_order)

        # Register particle editing actions
        self.listParticles.itemSelectionChanged.connect(self.select_particle)
        self.treeParticleBlocks.itemSelectionChanged.connect(self.select_particle_block)

        self.actionToolAdd.triggered.connect(self.add_particle)
        self.actionToolDelete.triggered.connect(self.delete_particles)
        self.actionToolClone.triggered.connect(self.clone_particles)
        self.actionToolCopy.triggered.connect(self.copy_particle)
        self.actionToolReplace.triggered.connect(self.replace_particle)
        self.actionToolExport.triggered.connect(self.export_particles)
        self.actionToolImport.triggered.connect(self.import_particles)

        self.textParticleName.textEdited.connect(self.set_particle_name)

        # Register effect editing actions
        self.listTextures.itemSelectionChanged.connect(self.select_texture)

        self.actionToolAdd.triggered.connect(self.add_or_import_textures)
        self.actionToolDelete.triggered.connect(self.delete_textures)
        self.actionToolExport.triggered.connect(self.export_textures)
        self.actionToolImport.triggered.connect(self.add_or_import_textures)

        self.emitterTranslationX.valueChanged.connect(lambda s: self.current_particle.dynamics_block.emitter_translation_x.set_val(s))
        self.emitterTranslationY.valueChanged.connect(lambda s: self.current_particle.dynamics_block.emitter_translation_y.set_val(s))
        self.emitterTranslationZ.valueChanged.connect(lambda s: self.current_particle.dynamics_block.emitter_translation_z.set_val(s))
        self.emitterRotationX.valueChanged.connect(lambda s: self.current_particle.dynamics_block.emitter_rotation_x_deg.set_val(s))
        self.emitterRotationY.valueChanged.connect(lambda s: self.current_particle.dynamics_block.emitter_rotation_y_deg.set_val(s))
        self.emitterRotationZ.valueChanged.connect(lambda s: self.current_particle.dynamics_block.emitter_rotation_z_deg.set_val(s))
        self.emitterScaleX.valueChanged.connect(lambda s: self.current_particle.dynamics_block.emitter_scale_x.set_val(s))
        self.emitterScaleY.valueChanged.connect(lambda s: self.current_particle.dynamics_block.emitter_scale_y.set_val(s))
        self.emitterScaleZ.valueChanged.connect(lambda s: self.current_particle.dynamics_block.emitter_scale_z.set_val(s))
        self.emitterDirectionX.valueChanged.connect(lambda s: self.current_particle.dynamics_block.emitter_direction_x.set_val(s))
        self.emitterDirectionY.valueChanged.connect(lambda s: self.current_particle.dynamics_block.emitter_direction_y.set_val(s))
        self.emitterDirectionZ.valueChanged.connect(lambda s: self.current_particle.dynamics_block.emitter_direction_z.set_val(s))
        self.initialVelocityOmni.valueChanged.connect(lambda s: self.current_particle.dynamics_block.initial_velocity_omni.set_val(s))
        self.initialVelocityRandom.valueChanged.connect(lambda s: self.current_particle.dynamics_block.initial_velocity_random.set_val(s))
        self.initialVelocityRatio.valueChanged.connect(lambda s: self.current_particle.dynamics_block.initial_velocity_ratio.set_val(s))
        self.initialVelocityAxis.valueChanged.connect(lambda s: self.current_particle.dynamics_block.initial_velocity_axis.set_val(s))
        self.initialVelocityDirection.valueChanged.connect(lambda s: self.current_particle.dynamics_block.initial_velocity_direction.set_val(s))
        self.lifetime.valueChanged.connect(lambda s: self.current_particle.dynamics_block.lifetime.set_val(s))
        self.startFrame.valueChanged.connect(lambda s: self.current_particle.dynamics_block.start_frame.set_val(s))
        self.rate.valueChanged.connect(lambda s: self.current_particle.dynamics_block.rate.set_val(s))
        self.rateStep.valueChanged.connect(lambda s: self.current_particle.dynamics_block.rate_step.set_val(s))
        self.lifetimeRandom.valueChanged.connect(lambda s: self.current_particle.dynamics_block.lifetime_random.set_val(s))
        self.maxFrame.valueChanged.connect(lambda s: self.current_particle.dynamics_block.max_frame.set_val(s))
        self.rateRandom.valueChanged.connect(lambda s: self.current_particle.dynamics_block.rate_random.set_val(s))
        self.divisionNumber.valueChanged.connect(lambda s: self.current_particle.dynamics_block.division_number.set_val(s))
        
        for volume_type in jsystem.jpac210.VolumeType:
            self.volumeType.addItem(volume_type.name)
        
        self.volumeType.currentIndexChanged.connect(self.set_particle_volume_type)
        self.volumeSweep.valueChanged.connect(lambda s: self.current_particle.dynamics_block.volume_sweep.set_val(s))
        self.volumeMinRadius.valueChanged.connect(lambda s: self.current_particle.dynamics_block.volume_minimum_radius.set_val(s))
        self.volumeSize.valueChanged.connect(lambda s: self.current_particle.dynamics_block.volume_size.set_val(s))
        self.airResistance.valueChanged.connect(lambda s: self.current_particle.dynamics_block.air_resistance.set_val(s))
        self.momentRandom.valueChanged.connect(lambda s: self.current_particle.dynamics_block.moment_random.set_val(s))
        self.spread.valueChanged.connect(lambda s: self.current_particle.dynamics_block.spread.set_val(s))
        self.followEmitter.toggled.connect(self.set_particle_follow_emitter)
        self.followEmitterChild.toggled.connect(self.set_particle_follow_emitter_child)
        self.fixedDensity.toggled.connect(self.set_particle_fixed_density)
        self.fixedInterval.toggled.connect(self.set_particle_fixed_interval)
        self.inheritScale.toggled.connect(self.set_particle_inherit_scale)

        for ftype in jsystem.jpac210.FieldType:
            self.fieldType.addItem(ftype.name)
        for ftype in jsystem.jpac210.FieldAddType:
            self.velocityType.addItem(ftype.name)

        self.fieldType.currentIndexChanged.connect(lambda s: self.get_current_field_block().flags.set_val_flag_name("FieldType", s))
        self.velocityType.currentIndexChanged.connect(lambda s: self.get_current_field_block().flags.set_val_flag_name("VelocityType", s))
        self.noInheritRotate.toggled.connect(lambda s: self.get_current_field_block().flags.set_val_flag_name("NoInheritRotate", s))
        self.airDrag.toggled.connect(lambda s: self.get_current_field_block().flags.set_val_flag_name("AirDrag", s))
        self.fadeUseEnterTime.toggled.connect(lambda s: self.get_current_field_block().flags.set_val_flag_name("FadeUseEnterTime", s))
        self.fadeUseDistanceTime.toggled.connect(lambda s: self.get_current_field_block().flags.set_val_flag_name("FadeUseDistanceTime", s))
        self.fadeUseFadeIn.toggled.connect(lambda s: self.get_current_field_block().flags.set_val_flag_name("FadeUseFadeIn", s))
        self.fadeUseFadeOut.toggled.connect(lambda s: self.get_current_field_block().flags.set_val_flag_name("FadeUseFadeOut", s))
        self.positionX.valueChanged.connect(lambda s: self.get_current_field_block().position_x.set_val(s))
        self.positionY.valueChanged.connect(lambda s: self.get_current_field_block().position_y.set_val(s))
        self.positionZ.valueChanged.connect(lambda s: self.get_current_field_block().position_z.set_val(s))
        self.directionX.valueChanged.connect(lambda s: self.get_current_field_block().direction_x.set_val(s))
        self.directionY.valueChanged.connect(lambda s: self.get_current_field_block().direction_y.set_val(s))
        self.directionZ.valueChanged.connect(lambda s: self.get_current_field_block().direction_z.set_val(s))
        self.param1.valueChanged.connect(lambda s: self.get_current_field_block().param_1.set_val(s))
        self.param2.valueChanged.connect(lambda s: self.get_current_field_block().param_2.set_val(s))
        self.param3.valueChanged.connect(lambda s: self.get_current_field_block().param_3.set_val(s))
        self.fadeIn.valueChanged.connect(lambda s: self.get_current_field_block().fade_in.set_val(s))
        self.fadeOut.valueChanged.connect(lambda s: self.get_current_field_block().fade_out.set_val(s))
        self.enterTime.valueChanged.connect(lambda s: self.get_current_field_block().enter_time.set_val(s))
        self.distanceTime.valueChanged.connect(lambda s: self.get_current_field_block().distance_time.set_val(s))
        self.cycle.valueChanged.connect(lambda s: self.get_current_field_block().cycle.set_val(s))

        self.keyframeTree.itemSelectionChanged.connect(self.select_keyframe)

        self.keyTime.valueChanged.connect(lambda s: self.set_keyframe_data("Time", s))
        self.keyValue.valueChanged.connect(lambda s: self.set_keyframe_data("Value", s))
        self.keyTangentIn.valueChanged.connect(lambda s: self.set_keyframe_data("TangentIn", s))
        self.keyTangentOut.valueChanged.connect(lambda s: self.set_keyframe_data("TangentOut", s))

        self.keyRemove.clicked.connect(self.remove_selected_keyframe)
        self.keyAdd.clicked.connect(self.add_keyframe)

        for key_type in jsystem.jpac210.KeyType:
            self.keyType.addItem(key_type.name)
        self.keyLoop.toggled.connect(lambda s: self.get_current_key_block().loop.set_val(s))
        self.keyType.currentIndexChanged.connect(lambda s: self.get_current_key_block().key_type.set_val(s))

        for mode in jsystem.jpac210.IndirectTextureMode:
            self.indirectTextureMode.addItem(mode.name)
        self.indirectTextureMode.currentIndexChanged.connect(lambda s: self.current_particle.ex_tex_shape.flags.set_val_flag_name("IndirectTextureMode", s))
        self.matrixScale.valueChanged.connect(lambda s: self.current_particle.ex_tex_shape.matrix_scale.set_val(s))
        self.indirectTextureIndex.valueChanged.connect(lambda s: self.current_particle.ex_tex_shape.indirect_texture_index.set_val(s))
        self.useSecondTextureIndex.toggled.connect(lambda s: self.current_particle.ex_tex_shape.flags.set_val_flag_name("UseSecondTextureIndex", s))
        self.secondTextureIndex.valueChanged.connect(lambda s: self.current_particle.ex_tex_shape.second_texture_index.set_val(s))
        self.indirectTexMatrix00.valueChanged.connect(lambda s: self.current_particle.ex_tex_shape.indirect_texture_matrix_0_0.set_val(s))
        self.indirectTexMatrix01.valueChanged.connect(lambda s: self.current_particle.ex_tex_shape.indirect_texture_matrix_0_1.set_val(s))
        self.indirectTexMatrix02.valueChanged.connect(lambda s: self.current_particle.ex_tex_shape.indirect_texture_matrix_0_2.set_val(s))
        self.indirectTexMatrix10.valueChanged.connect(lambda s: self.current_particle.ex_tex_shape.indirect_texture_matrix_1_0.set_val(s))
        self.indirectTexMatrix11.valueChanged.connect(lambda s: self.current_particle.ex_tex_shape.indirect_texture_matrix_1_1.set_val(s))
        self.indirectTexMatrix12.valueChanged.connect(lambda s: self.current_particle.ex_tex_shape.indirect_texture_matrix_1_2.set_val(s))

        for x in jsystem.jpac210.ShapeType:
            self.childShapeType.addItem(x.name)
        for x in jsystem.jpac210.RotationType:
            self.childRotationType.addItem(x.name)
        for x in jsystem.jpac210.DirectionType:
            self.childDirectionType.addItem(x.name)
        for x in jsystem.jpac210.PlaneType:
            self.childPlaneType.addItem(x.name)
        
        self.childShapeType.currentIndexChanged.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("ShapeType", s))
        self.childRotationType.currentIndexChanged.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("RotationType", s))
        self.childDirectionType.currentIndexChanged.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("DirectionType", s))
        self.childPlaneType.currentIndexChanged.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("PlaneType", s))
        self.childFieldEnabled.toggled.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("IsEnableField", s))
        self.childScaleOutEnabled.toggled.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("IsEnableScaleOut", s))
        self.childAlphaOutEnabled.toggled.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("IsEnableAlphaOut", s))
        self.childRotationEnabled.toggled.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("IsEnableRotate", s))
        self.childGlobalScale2DX.valueChanged.connect(lambda s: self.get_current_block_data().global_scale_2d_x.set_val(s))
        self.childGlobalScale2DY.valueChanged.connect(lambda s: self.get_current_block_data().global_scale_2d_y.set_val(s))
        self.childPrimaryColor.textChanged.connect(lambda s: self.get_current_block_data().primary_color.set_val(bytes.fromhex(self.childPrimaryColor.displayText())))
        self.childEnvironmentColor.textChanged.connect(lambda s: self.get_current_block_data().environment_color.set_val(bytes.fromhex(self.childEnvironmentColor.displayText())))
        self.childTextureIndex.valueChanged.connect(lambda s: self.get_current_block_data().texture_index.set_val(s))
        self.childScaleInherited.toggled.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("IsInheritedScale", s))
        self.childInheritScale.valueChanged.connect(lambda s: self.get_current_block_data().inherit_scale.set_val(s))
        self.childAlphaInherited.toggled.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("IsInheritedAlpha", s))
        self.childInheritAlpha.valueChanged.connect(lambda s: self.get_current_block_data().inherit_alpha.set_val(s))
        self.childRGBInherited.toggled.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("IsInheritedRGB", s))
        self.childInheritRGB.valueChanged.connect(lambda s: self.get_current_block_data().inherit_rgb.set_val(s))
        self.childTiming.valueChanged.connect(lambda s: self.get_current_block_data().timing.set_val(s))
        self.childLife.valueChanged.connect(lambda s: self.get_current_block_data().life.set_val(s))
        self.childRate.valueChanged.connect(lambda s: self.get_current_block_data().rate.set_val(s))
        self.childStep.valueChanged.connect(lambda s: self.get_current_block_data().step.set_val(s))
        self.childRotateSpeed.valueChanged.connect(lambda s: self.get_current_block_data().rotate_speed.set_val(s))
        self.childVelocityInfluenceRate.valueChanged.connect(lambda s: self.get_current_block_data().velocity_influence_rate.set_val(s))
        self.childBaseVelocity.valueChanged.connect(lambda s: self.get_current_block_data().base_velocity.set_val(s))
        self.childBaseVelocityRandom.valueChanged.connect(lambda s: self.get_current_block_data().base_velocity_random.set_val(s))
        self.childGravity.valueChanged.connect(lambda s: self.get_current_block_data().gravity.set_val(s))
        self.childPositionRandom.valueChanged.connect(lambda s: self.get_current_block_data().position_random.set_val(s))

        for x in jsystem.jpac210.CalcScaleAnimType:
            self.extraScaleAnimTypeX.addItem(x.name)
            self.extraScaleAnimTypeY.addItem(x.name)

        self.extraIsDiffXY.toggled.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("IsDiffXY", s))
        self.extraSinWaveEnabled.toggled.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("IsEnableSinWave", s))
        self.extraPivotX.valueChanged.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("PivotX", s))
        self.extraPivotY.valueChanged.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("PivotY", s))
        self.extraScaleEnabled.toggled.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("IsEnableScale", s))
        self.extraScaleInTiming.valueChanged.connect(lambda s: self.get_current_block_data().scale_in_timing.set_val(s))
        self.extraScaleInValueX.valueChanged.connect(lambda s: self.get_current_block_data().scale_in_value_x.set_val(s))
        self.extraScaleInValueY.valueChanged.connect(lambda s: self.get_current_block_data().scale_in_value_y.set_val(s))
        self.extraScaleAnimXMaxFrame.valueChanged.connect(lambda s: self.get_current_block_data().scale_animation_x_max_frame.set_val(s))
        self.extraScaleAnimTypeX.currentIndexChanged.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("ScaleAnimTypeX", s))
        self.extraScaleOutRandom.valueChanged.connect(lambda s: self.get_current_block_data().scale_out_random.set_val(s))
        self.extraScaleOutTiming.valueChanged.connect(lambda s: self.get_current_block_data().scale_out_timing.set_val(s))
        self.extraScaleOutValueX.valueChanged.connect(lambda s: self.get_current_block_data().scale_out_value_x.set_val(s))
        self.extraScaleOutValueY.valueChanged.connect(lambda s: self.get_current_block_data().scale_out_value_y.set_val(s))
        self.extraScaleAnimYMaxFrame.valueChanged.connect(lambda s: self.get_current_block_data().scale_animation_y_max_frame.set_val(s))
        self.extraScaleAnimTypeY.currentIndexChanged.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("ScaleAnimTypeY", s))
        self.extraAlphaEnabled.toggled.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("IsEnableAlpha", s))
        self.extraAlphaInTiming.valueChanged.connect(lambda s: self.get_current_block_data().alpha_in_timing.set_val(s))
        self.extraAlphaInValue.valueChanged.connect(lambda s: self.get_current_block_data().alpha_in_value.set_val(s))
        self.extraAlphaBaseValue.valueChanged.connect(lambda s: self.get_current_block_data().alpha_base_value.set_val(s))
        self.extraAlphaWaveRandom.valueChanged.connect(lambda s: self.get_current_block_data().alpha_wave_random.set_val(s))
        self.extraAlphaOutTiming.valueChanged.connect(lambda s: self.get_current_block_data().alpha_out_timing.set_val(s))
        self.extraAlphaOutValue.valueChanged.connect(lambda s: self.get_current_block_data().alpha_out_value.set_val(s))
        self.extraAlphaWaveFrequency.valueChanged.connect(lambda s: self.get_current_block_data().alpha_wave_frequency.set_val(s))
        self.extraAlphaWaveAmplitude.valueChanged.connect(lambda s: self.get_current_block_data().alpha_wave_amplitude.set_val(s))
        self.extraRotationEnabled.toggled.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("IsEnableRotate", s))
        self.extraRotationAngle.valueChanged.connect(lambda s: self.get_current_block_data().rotate_angle.set_val(s))
        self.extraRotationSpeed.valueChanged.connect(lambda s: self.get_current_block_data().rotate_speed.set_val(s))
        self.extraRotationDirection.valueChanged.connect(lambda s: self.get_current_block_data().rotate_direction.set_val(s))
        self.extraRotationAngleRandom.valueChanged.connect(lambda s: self.get_current_block_data().rotate_angle_random.set_val(s))
        self.extraRotationSpeedRandom.valueChanged.connect(lambda s: self.get_current_block_data().rotate_speed_random.set_val(s))

        self.baseTilingS.addItem("1.0")
        self.baseTilingS.addItem("2.0")
        self.baseTilingT.addItem("1.0")
        self.baseTilingT.addItem("2.0")

        for x in jsystem.jpac210.BlendMode:
            self.baseBlendMode.addItem(x.name)
        for x in jsystem.jpac210.BlendFactor:
            self.baseBlendSourceFactor.addItem(x.name)
            self.baseBlendDestinationFactor.addItem(x.name)
        for x in jsystem.jpac210.DirectionType:
            self.baseDirectionType.addItem(x.name)
        for x in jsystem.jpac210.RotationType:
            self.baseRotationType.addItem(x.name)
        for x in jsystem.jpac210.ShapeType:
            self.baseShapeType.addItem(x.name)
        for x in jsystem.jpac210.PlaneType:
            self.basePlaneType.addItem(x.name)
        for x in jsystem.jpac210.CompareType:
            self.baseDepthCompareType.addItem(x.name)
            self.baseAlphaCompareType0.addItem(x.name)
            self.baseAlphaCompareType1.addItem(x.name)
        for x in jsystem.jpac210.AlphaOperator:
            self.baseAlphaOperator.addItem(x.name)
        for x in jsystem.jpac210.CalcIndexType:
            self.baseTextureCalculateIndexType.addItem(x.name)
            self.baseColorCalculateIndexType.addItem(x.name)

        self.basePrimaryColorTree.itemSelectionChanged.connect(self.select_primary_color_frame)
        self.basePrimaryColorFrame.valueChanged.connect(lambda s: self.set_color_frame_data("Frame", s, self.basePrimaryColorTree))
        self.basePrimaryColorColor.textChanged.connect(lambda s: self.set_color_frame_data("Color", bytes.fromhex(self.basePrimaryColorColor.displayText()), self.basePrimaryColorTree))
        self.basePrimaryColorDelete.clicked.connect(lambda: self.remove_selected_color_frame(self.basePrimaryColorTree))
        self.basePrimaryColorAdd.clicked.connect(lambda: self.add_color_frame(self.basePrimaryColorTree))
        self.basePrimaryColorAnimEnabled.toggled.connect(self.set_primary_color_enabled)

        self.baseEnvironmentColorTree.itemSelectionChanged.connect(self.select_environment_color_frame)
        self.baseEnvironmentColorFrame.valueChanged.connect(lambda s: self.set_color_frame_data("Frame", s, self.baseEnvironmentColorTree))
        self.baseEnvironmentColorColor.textChanged.connect(lambda s: self.set_color_frame_data("Color", bytes.fromhex(self.baseEnvironmentColorColor.displayText()), self.baseEnvironmentColorTree))
        self.baseEnvironmentColorDelete.clicked.connect(lambda: self.remove_selected_color_frame(self.baseEnvironmentColorTree))
        self.baseEnvironmentColorAdd.clicked.connect(lambda: self.add_color_frame(self.baseEnvironmentColorTree))
        self.baseEnvironmentColorAnimEnabled.toggled.connect(self.set_environment_color_enabled)
        
        self.baseTextureIndexData.itemChanged.connect(self.texture_index_changed)
        self.baseTextureIndexData.itemSelectionChanged.connect(self.selection_changed_texture_animation)
        self.baseEnableTextureAnimation.toggled.connect(self.enable_texture_animation)
        self.baseTextureIndexDelete.clicked.connect(self.remove_selected_texture_index)
        self.baseTextureIndexAdd.clicked.connect(self.add_texture_index)

        self.baseTextureScrollAnimEnabled.toggled.connect(self.enable_texture_scroll_anim)
        
        self.baseProjectionEnabled.toggled.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("IsEnableProjection", s))
        self.baseDrawForwardAhead.toggled.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("IsDrawForwardAhead", s))
        self.baseDrawPrintAhead.toggled.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("IsDrawPrintAhead", s))
        self.baseTilingS.currentIndexChanged.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("DoubleTilingS", bool(s)))
        self.baseTilingT.currentIndexChanged.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("DoubleTilingT", bool(s)))
        self.baseDontDrawParent.toggled.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("IsNoDrawParent", s))
        self.baseDontDrawChild.toggled.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("IsNoDrawChild", s))
        self.baseBaseSizeX.valueChanged.connect(lambda s: self.get_current_block_data().base_size_x.set_val(s))
        self.baseBaseSizeY.valueChanged.connect(lambda s: self.get_current_block_data().base_size_y.set_val(s))
        self.baseBlendMode.currentIndexChanged.connect(lambda s: self.get_current_block_data().blend_mode_flags.set_val_flag_name("BlendMode", s))
        self.baseBlendSourceFactor.currentIndexChanged.connect(lambda s: self.get_current_block_data().blend_mode_flags.set_val_flag_name("SourceFactor", s))
        self.baseBlendDestinationFactor.currentIndexChanged.connect(lambda s: self.get_current_block_data().blend_mode_flags.set_val_flag_name("DestinationFactor", s))
        self.baseDepthTest.toggled.connect(lambda s: self.get_current_block_data().z_mode_flags.set_val_flag_name("DepthTest", s))
        self.baseDepthCompareType.currentIndexChanged.connect(lambda s: self.get_current_block_data().z_mode_flags.set_val_flag_name("DepthCompareType", s))
        self.baseDepthWrite.toggled.connect(lambda s: self.get_current_block_data().z_mode_flags.set_val_flag_name("DepthWrite", s))
        self.baseShapeType.currentIndexChanged.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("ShapeType", s))
        self.baseDirectionType.currentIndexChanged.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("DirectionType", s))
        self.baseRotationType.currentIndexChanged.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("RotationType", s))
        self.basePlaneType.currentIndexChanged.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("PlaneType", s))
        self.baseAlphaCompareType0.currentIndexChanged.connect(lambda s: self.get_current_block_data().alpha_compare_flags.set_val_flag_name("AlphaCompareType0", s))
        self.baseAlphaCompareType1.currentIndexChanged.connect(lambda s: self.get_current_block_data().alpha_compare_flags.set_val_flag_name("AlphaCompareType1", s))
        self.baseAlphaOperator.currentIndexChanged.connect(lambda s: self.get_current_block_data().alpha_compare_flags.set_val_flag_name("AlphaOperator", s))
        self.baseAlphaReference0.valueChanged.connect(lambda s: self.get_current_block_data().alpha_reference_0.set_val(s))
        self.baseAlphaReference1.valueChanged.connect(lambda s: self.get_current_block_data().alpha_reference_1.set_val(s))
        self.baseAlphaInSelect.valueChanged.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("AlphaInSelect", s))
        self.baseGlobalTextureAnimation.toggled.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("IsGlobalTextureAnimation", s))
        self.baseTextureCalculateIndexType.currentIndexChanged.connect(lambda s: self.get_current_block_data().texture_flags.set_val_flag_name("TexCalcIndexType", s))
        self.baseTextureIndex.valueChanged.connect(lambda s: self.get_current_block_data().texture_index.set_val(s))
        self.baseColorCalculateIndexType.currentIndexChanged.connect(lambda s: self.get_current_block_data().color_flags.set_val_flag_name("ColorCalcIndexType", s))
        self.basePrimaryColor.textChanged.connect(lambda s: self.get_current_block_data().primary_color.set_val(bytes.fromhex(self.basePrimaryColor.displayText())))
        self.baseEnvironmentColor.textChanged.connect(lambda s: self.get_current_block_data().environment_color.set_val(bytes.fromhex(self.baseEnvironmentColor.displayText())))
        self.baseColorLoopOffsetMask.valueChanged.connect(lambda s: self.get_current_block_data().color_loop_offset_mask.set_val(s))
        self.baseColorInSelect.valueChanged.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("ColorInSelect", s))
        self.baseColorAnimationMaxFrame.valueChanged.connect(lambda s: self.get_current_block_data().color_animation_max_frame.set_val(s))
        self.baseGlobalColorAnimation.toggled.connect(lambda s: self.get_current_block_data().flags.set_val_flag_name("IsGlobalColorAnimation", s))
        self.baseAnimationRandom.valueChanged.connect(lambda s: self.get_current_block_data().animation_random.set_val(s))
        self.baseIndexLoopOffsetMask.valueChanged.connect(lambda s: self.get_current_block_data().texture_index_loop_offset_mask.set_val(s))
        self.baseInitialTranslationX.valueChanged.connect(lambda s: self.get_current_block_data().tex_init_trans_x.set_val(s))
        self.baseInitialTranslationY.valueChanged.connect(lambda s: self.get_current_block_data().tex_init_trans_y.set_val(s))
        self.baseInitialScaleX.valueChanged.connect(lambda s: self.get_current_block_data().tex_init_scale_x.set_val(s))
        self.baseInitialScaleY.valueChanged.connect(lambda s: self.get_current_block_data().tex_init_scale_y.set_val(s))
        self.baseInitialRotation.valueChanged.connect(lambda s: self.get_current_block_data().tex_init_rot.set_val(s))
        self.baseIncrementRotation.valueChanged.connect(lambda s: self.get_current_block_data().tex_inc_rot.set_val(s))
        self.baseIncrementTranslationX.valueChanged.connect(lambda s: self.get_current_block_data().tex_inc_trans_x.set_val(s))
        self.baseIncrementTranslationY.valueChanged.connect(lambda s: self.get_current_block_data().tex_inc_trans_y.set_val(s))
        self.baseIncrementScaleX.valueChanged.connect(lambda s: self.get_current_block_data().tex_inc_scale_x.set_val(s))
        self.baseIncrementScaleY.valueChanged.connect(lambda s: self.get_current_block_data().tex_inc_scale_y.set_val(s))

        self.btnAddBlock.clicked.connect(self.show_add_block_menu)
        self.btnRemoveBlock.clicked.connect(self.remove_selected_particle_block)

        # Create preferences window and menu function
        self.preferences = PgpPreferencesWindow(self)
        self.actionPreferences.triggered.connect(self.preferences.show)

        # Finalize UI
        self.actionAbout.triggered.connect(self.show_about)
        self.tabContents.currentChanged.connect(self.update_toolbar)
        self.enable_all_components(False)
        self.hide_all_particle_settings_tabs()
        self.show()

    @staticmethod
    def text_block_to_list(text):
        return text.replace(" ", "").replace("\r", "").split("\n")

    # ---------------------------------------------------------------------------------------------
    # Particle data I/O
    # ---------------------------------------------------------------------------------------------
    def select_open_particle_data_file(self) -> str:
        filters = "ARC files (*.arc);;RARC files (*.rarc)"
        return QtWidgets.QFileDialog.getOpenFileName(self, "Load particle data from...", directory=get_last_file(), filter=filters)[0]

    def select_save_particle_data_file(self) -> str:
        filters = "ARC files (*.arc);;RARC files (*.rarc)"
        return QtWidgets.QFileDialog.getSaveFileName(self, "Save particle data to...", directory=get_last_file(), filter=filters)[0]

    def open_particle_data(self):
        particle_file_name = self.select_open_particle_data_file()

        if len(particle_file_name) == 0:
            return

        set_last_file(particle_file_name)
        self.reset_editor()

        self.particle_data = mrformats.ParticleData()
        self.particle_data_file = particle_file_name
        self.current_effect = None
        self.current_particle = None
        self.current_texture = None

        # Try to unpack particle data
        try:
            self.effect_arc = jsystem.JKRArchive()
            self.effect_arc.unpack(pyaurum.read_bin_file(self.particle_data_file))

            self.particle_data.unpack_rarc(self.effect_arc)
        except Exception as e:  # Will be handled better in the future, smh
            self.status("An error occured while loading particle data. See output for details.", StatusColor.ERROR)
            print(e)
            return

        # Populate data
        for effect in self.particle_data.effects:
            self.listEffects.addItem(effect.description())

        for particle in self.particle_data.particles:
            self.listParticles.addItem(particle.name)

        for texture in self.particle_data.textures.keys():
            self.listTextures.addItem(texture)

        self.enable_all_components(True)
        self.widgetEffects.setEnabled(False)

        self.status(f"Successfully loaded particle data from \"{self.particle_data_file}\".", StatusColor.INFO)

    def save_particle_data(self):
        if self.particle_data is None or self.contains_errors():
            return

        if self.particle_data_file is None:
            particle_file_name = self.select_save_particle_data_file()
            if len(particle_file_name) == 0:
                return

            set_last_file(particle_file_name)
            self.particle_data_file = particle_file_name
        self.save_particle_data_to_file()

    def save_as_particle_data(self):
        if self.particle_data is None or self.contains_errors():
            return

        particle_file_name = self.select_save_particle_data_file()
        if len(particle_file_name) == 0:
            return

        set_last_file(particle_file_name)
        self.particle_data_file = particle_file_name
        self.save_particle_data_to_file()

    def save_particle_data_to_file(self):
        # Pack particle data into RARC folder
        self.particle_data.pack_rarc(self.effect_arc)

        # Pack Effect.arc, try to compress the buffer and write to output file.
        print("Pack RARC archive...")
        packed_arc = self.effect_arc.pack()

        if is_compress_arc():
            compressed = jsystem.write_file_try_szs_external(self.particle_data_file, packed_arc, get_wszst_rate())

            if compressed:
                self.status(f"Saved and compressed particle data to \"{self.particle_data_file}\".", StatusColor.INFO)
            else:
                self.status(f"Saved particle data to \"{self.particle_data_file}\". Compression failed.", StatusColor.WARN)
        else:
            pyaurum.write_file(self.particle_data_file, packed_arc)
            self.status(f"Saved particle data to \"{self.particle_data_file}\".", StatusColor.INFO)

    def contains_errors(self):
        # todo: improve this, duh
        error_log = list()
        more_than_10 = False

        def log_error(message: str):
            nonlocal more_than_10
            if len(error_log) == 10:
                more_than_10 = True
            else:
                error_log.append(message)
            return more_than_10

        # Check particles for errors
        particle_names = list()

        for particle in self.particle_data.particles:
            particle_name = particle.name

            # Duplicate particle name?
            if particle_name in particle_names:
                if log_error(f"Duplicate particle \"{particle_name}\""):
                    break

            # Missing textures?
            for texture_name in particle.texture_names:
                if texture_name not in self.particle_data.textures:
                    if log_error(f"Missing texture \"{texture_name}\""):
                        break

            particle_names.append(particle_name)

        # No errors were found
        if len(error_log) == 0:
            return False
        # Show critical error message if errors are found
        else:
            errors_message = "\n".join(error_log)
            errors_message = "Can't save particle data due to these errors:\n\n" + errors_message

            if more_than_10:
                errors_message += "\n\n...and more!"

            self.show_critical(errors_message)
            return True

    # ---------------------------------------------------------------------------------------------
    # General UI helpers
    # ---------------------------------------------------------------------------------------------
    def status(self, text: str, status: int, duration: int = 5000):
        if status == StatusColor.INFO:
            color = "green"
        if status == StatusColor.WARN:
            color = "orange"
        if status == StatusColor.ERROR:
            color = "red"

        self.statusBar.setStyleSheet(f"QStatusBar{{padding:8px;color:{color};}}")
        self.statusBar.showMessage(text, duration)

    def show_information(self, text: str):
        QtWidgets.QMessageBox.information(self, APP_TITLE, text)

    def show_warning(self, text: str):
        QtWidgets.QMessageBox.warning(self, APP_TITLE, text)

    def show_critical(self, text: str):
        QtWidgets.QMessageBox.critical(self, APP_TITLE, text)

    def get_editor_mode(self):
        current_tab = self.tabContents.currentIndex()

        # todo: particle stuff

        return PgpEditorMode(current_tab)

    def enable_all_components(self, state: bool):
        self.toolBar.setEnabled(state)
        self.tabEffects.setEnabled(state)
        self.tabParticles.setEnabled(state)
        self.tabTextures.setEnabled(state)

    def reset_editor(self):
        self.listEffects.clear()
        self.listParticles.clear()
        self.listTextures.clear()
        self.treeParticleBlocks.clear()
        self.enable_all_components(False)

    def update_toolbar(self):
        if self.get_editor_mode() == PgpEditorMode.TEXTURE:
            self.actionToolClone.setEnabled(False)
            self.actionToolCopy.setEnabled(False)
            self.actionToolReplace.setEnabled(False)
        else:
            self.actionToolClone.setEnabled(True)
            self.actionToolCopy.setEnabled(True)
            self.actionToolReplace.setEnabled(True)

    def show_about(self):
        self.show_information("Original by Aurum. Unofficial fork by AwesomeTMC.\nReport any bugs and problems here:\nhttps://github.com/AwesomeTMC/pygapa")

    # ---------------------------------------------------------------------------------------------
    # Effect editing
    # ---------------------------------------------------------------------------------------------
    def select_effect(self):
        # Make sure only one effect is selected
        if len(self.listEffects.selectedItems()) != 1:
            self.widgetEffects.setEnabled(False)
            self.current_effect = None
            return

        # Enable all effect editing components and get currently selected effect instance
        self.widgetEffects.setEnabled(True)
        self.current_effect = self.particle_data.effects[self.listEffects.currentRow()]

        # Block signals temporarily to prevent invoking textChanged
        self.textEffectAnimName.blockSignals(True)
        self.textEffectEffectName.blockSignals(True)

        # Populate effect data for currently selected item
        self.textEffectGroupName.setText(self.current_effect.group_name)
        self.textEffectAnimName.setPlainText("\n".join(self.current_effect.anim_name))
        self.checkEffectContinueAnimEnd.setChecked(self.current_effect.continue_anim_end)
        self.textEffectUniqueName.setText(self.current_effect.unique_name)
        self.textEffectEffectName.setPlainText("\n".join(self.current_effect.effect_name))
        self.textEffectParentName.setText(self.current_effect.parent_name)
        self.textEffectJointName.setText(self.current_effect.joint_name)
        self.spinnerEffectOffsetX.setValue(self.current_effect.offset_x)
        self.spinnerEffectOffsetY.setValue(self.current_effect.offset_y)
        self.spinnerEffectOffsetZ.setValue(self.current_effect.offset_z)
        self.spinnerEffectStartFrame.setValue(self.current_effect.start_frame)
        self.spinnerEffectEndFrame.setValue(self.current_effect.end_frame)
        self.checkEffectAffectT.setChecked(self.current_effect.affect["T"])
        self.checkEffectAffectR.setChecked(self.current_effect.affect["R"])
        self.checkEffectAffectS.setChecked(self.current_effect.affect["S"])
        self.checkEffectFollowT.setChecked(self.current_effect.follow["T"])
        self.checkEffectFollowR.setChecked(self.current_effect.follow["R"])
        self.checkEffectFollowS.setChecked(self.current_effect.follow["S"])
        self.spinnerEffectScaleValue.setValue(self.current_effect.scale_value)
        self.spinnerEffectRateValue.setValue(self.current_effect.rate_value)
        self.spinnerEffectLightAffectValue.setValue(self.current_effect.light_affect_value)
        self.textEffectPrmColor.setText(self.current_effect.prm_color)
        self.textEffectEnvColor.setText(self.current_effect.env_color)
        self.comboEffectDrawOrder.setCurrentIndex(mrformats.PARTICLE_DRAW_ORDERS.index(self.current_effect.draw_order))

        # Release blocked signals
        self.textEffectAnimName.blockSignals(False)
        self.textEffectEffectName.blockSignals(False)

    def add_effect(self):
        if self.get_editor_mode() != PgpEditorMode.EFFECT:
            return

        # Create new effect
        effect = mrformats.ParticleEffect()
        self.particle_data.effects.append(effect)

        # Update effects list
        new_index = self.listEffects.count()
        self.listEffects.addItem(effect.description())
        self.listEffects.clearSelection()
        self.listEffects.setCurrentRow(new_index)

        self.status("Added new effect entry.", StatusColor.INFO)

    def delete_effects(self):
        if self.get_editor_mode() != PgpEditorMode.EFFECT:
            return
        if len(self.listEffects.selectedItems()) == 0:
            self.status("No effect(s) selected!", StatusColor.ERROR)
            return

        # Get selected list indexes
        delete_indexes = [i.row() for i in self.listEffects.selectionModel().selectedIndexes()]

        # The selected indexes are shuffled, so we remove entries starting from the end of the list
        delete_indexes.sort(reverse=True)

        # Go through indexes and delete list item and the actual effect entry
        for delete_index in delete_indexes:
            self.listEffects.takeItem(delete_index)
            self.particle_data.effects.pop(delete_index)

        self.status(f"Deleted {len(delete_indexes)} effect(s).", StatusColor.INFO)

    def clone_effects(self):
        if self.get_editor_mode() != PgpEditorMode.EFFECT:
            return
        if len(self.listEffects.selectedItems()) == 0:
            self.status("No effect(s) selected!", StatusColor.ERROR)
            return

        # Get selected list indexes
        clone_indexes = [i.row() for i in self.listEffects.selectionModel().selectedIndexes()]

        # The selected indexes are shuffled, but we want to retain the original order of the clones
        clone_indexes.sort()

        # Make sure the first clone is selected afterwards
        new_index = self.listEffects.count()

        # Create deep clones of all effects and populate them to the respective lists
        for clone_index in clone_indexes:
            clone = copy.deepcopy(self.particle_data.effects[clone_index])
            self.particle_data.effects.append(clone)
            self.listEffects.addItem(clone.description())

        # Update list selection
        self.listEffects.clearSelection()
        self.listEffects.setCurrentRow(new_index)

        self.status(f"Cloned {len(clone_indexes)} effect(s).", StatusColor.INFO)

    def copy_effect(self):
        if self.get_editor_mode() != PgpEditorMode.EFFECT:
            return
        if self.current_effect is None:
            self.status("No effect selected!", StatusColor.ERROR)
            return

        self.copied_effect = copy.deepcopy(self.particle_data.effects[self.listEffects.currentRow()])

        self.status(f"Copied effect {self.copied_effect.description()}.", StatusColor.INFO)

    def replace_effect(self):
        if self.get_editor_mode() != PgpEditorMode.EFFECT:
            return
        if self.current_effect is None:
            self.status("No effect selected!", StatusColor.ERROR)
            return
        if self.copied_effect is None:
            self.status("No effect copy available!", StatusColor.ERROR)
            return

        # Replace current effect, we want to preserve references to current effect and its members
        old_description = self.current_effect.description()
        self.current_effect.replace_with(self.copied_effect)

        # Update widgets and list
        self.select_effect()
        self.update_current_effect_list_item()

        self.status(f"Replaced effect {old_description} with {self.copied_effect.description()}.", StatusColor.INFO)

    def export_effects(self):
        if self.get_editor_mode() != PgpEditorMode.EFFECT:
            return
        if len(self.listEffects.selectedItems()) == 0:
            self.status("No effect(s) selected!", StatusColor.ERROR)
            return

        # Get file to export data to
        export_file = QtWidgets.QFileDialog.getSaveFileName(self, "Export to JSON file...", filter="JSON file (*.json)")[0]

        if len(export_file) == 0:
            return

        # Get selected list indexes
        export_indexes = [i.row() for i in self.listEffects.selectionModel().selectedIndexes()]
        export_indexes.sort()

        # Get effects to be exported as a list of JSON objects
        exported_effects = list()

        for export_index in export_indexes:
            exported_effects.append(self.particle_data.effects[export_index].pack_json())

        # Write JSON file
        pyaurum.write_json_file(export_file, exported_effects)

        self.status(f"Exported {len(export_indexes)} effect(s) to \"{export_file}\".", StatusColor.INFO)

    def import_effects(self):
        if self.get_editor_mode() != PgpEditorMode.EFFECT:
            return

        import_file = QtWidgets.QFileDialog.getOpenFileName(self, "Import from JSON file...", filter="JSON file (*.json)")[0]

        if len(import_file) == 0:
            return

        try:
            imported_effects = pyaurum.read_json_file(import_file)
        except Exception as e:
            self.show_critical(f"An error occured when importing from \"{import_file}\". See output for details.")
            print(e)
            return

        # Select the first imported entry
        new_index = self.listEffects.count()

        # Convert JSON entries to effects and add them to the respective lists
        for effect_entry in imported_effects:
            effect = mrformats.ParticleEffect()
            effect.unpack_json(effect_entry)

            self.particle_data.effects.append(effect)
            self.listEffects.addItem(effect.description())

        # Update effects list
        self.listEffects.clearSelection()
        self.listEffects.setCurrentRow(new_index)

        self.status(f"Imported {len(imported_effects)} effect(s) from \"{import_file}\".", StatusColor.INFO)

    def update_current_effect_list_item(self):
        self.listEffects.selectedItems()[0].setText(self.current_effect.description())

    def set_effect_group_name(self, text: str):
        self.current_effect.group_name = text
        self.update_current_effect_list_item()

    def set_effect_unique_name(self, text: str):
        self.current_effect.unique_name = text
        self.update_current_effect_list_item()

    def set_effect_effect_name(self):
        self.current_effect.effect_name = self.text_block_to_list(self.textEffectEffectName.toPlainText())

    def set_effect_parent_name(self, text: str):
        self.current_effect.parent_name = text

    def set_effect_joint_name(self, text: str):
        self.current_effect.joint_name = text

    def set_effect_anim_name(self):
        self.current_effect.anim_name = self.text_block_to_list(self.textEffectAnimName.toPlainText())

    def set_effect_continue_anim_end(self, checked: bool):
        self.current_effect.continue_anim_end = checked

    def set_effect_start_frame(self, val: int):
        self.current_effect.start_frame = val

    def set_effect_end_frame(self, val: int):
        self.current_effect.end_frame = val

    def set_effect_offset_x(self, val: float):
        self.current_effect.offset_x = round(val, 7)

    def set_effect_offset_y(self, val: float):
        self.current_effect.offset_y = round(val, 7)

    def set_effect_offset_z(self, val: float):
        self.current_effect.offset_z = round(val, 7)

    def set_effect_affect_flag(self, checked: bool, flag: str):
        self.current_effect.affect[flag] = checked

    def set_effect_follow_flag(self, checked: bool, flag: str):
        self.current_effect.follow[flag] = checked

    def set_effect_scale_value(self, val: float):
        self.current_effect.scale_value = round(val, 7)

    def set_effect_rate_value(self, val: float):
        self.current_effect.rate_value = round(val, 7)

    def set_effect_light_affect_value(self, val: float):
        self.current_effect.light_affect_value = round(val, 7)

    def set_effect_prm_color(self, text: str):
        self.current_effect.prm_color = text

    def set_effect_env_color(self, text: str):
        self.current_effect.env_color = text

    def set_effect_draw_order(self, index: int):
        self.current_effect.draw_order = mrformats.PARTICLE_DRAW_ORDERS[index]

    # ---------------------------------------------------------------------------------------------
    # Particle editing
    # ---------------------------------------------------------------------------------------------
    def select_particle(self):
        self.treeParticleBlocks.clear()

        # Make sure only one effect is selected
        if len(self.listParticles.selectedItems()) != 1:
            self.widgetParticles.setEnabled(False)
            self.btnAddBlock.setEnabled(False)
            self.current_particle = None
            return

        # Enable all effect editing components and get currently selected effect instance
        self.widgetParticles.setEnabled(True)
        self.btnAddBlock.setEnabled(True)
        self.current_particle = self.particle_data.particles[self.listParticles.currentRow()]

        # Block signals temporarily to prevent invoking textChanged
        self.textParticleTextures.blockSignals(True)

        # Populate effect data for currently selected item
        self.textParticleName.setText(self.current_particle.name)
        self.textParticleTextures.setPlainText("\n".join(self.current_particle.texture_names))

        # Populate blocks and their entries
        self.populate_particle_blocks()

        self.hide_all_particle_settings_tabs()

        self.btnRemoveBlock.setEnabled(False)

        # Release blocked signals
        self.textParticleTextures.blockSignals(False)

    def populate_particle_blocks(self):
        if self.current_particle.dynamics_block:
            node = create_data_node("Dynamics", PgpEditorMode.DYNAMICS_BLOCK, self.current_particle.dynamics_block)
            self.treeParticleBlocks.addTopLevelItem(node)

        if self.current_particle.field_blocks is not None:
            node = create_data_node("Field blocks", PgpEditorMode.FIELD_BLOCKS, self.current_particle.field_blocks)
            self.treeParticleBlocks.addTopLevelItem(node)

            for field_block in self.current_particle.field_blocks:
                block_node = create_data_node("Field block", PgpEditorMode.FIELD_BLOCK, field_block)
                node.addChild(block_node)

        if self.current_particle.key_blocks is not None:
            node = create_data_node("Key blocks", PgpEditorMode.KEY_BLOCKS, self.current_particle.key_blocks)
            self.treeParticleBlocks.addTopLevelItem(node)

            for key_block in self.current_particle.key_blocks:
                block_node = create_data_node("Key block", PgpEditorMode.KEY_BLOCK, key_block)
                node.addChild(block_node)

        if self.current_particle.base_shape:
            node = create_data_node("Base shape", PgpEditorMode.BASE_SHAPE, self.current_particle.base_shape)
            self.treeParticleBlocks.addTopLevelItem(node)

        if self.current_particle.extra_shape:
            node = create_data_node("Extra shape", PgpEditorMode.EXTRA_SHAPE, self.current_particle.extra_shape)
            self.treeParticleBlocks.addTopLevelItem(node)

        if self.current_particle.child_shape:
            node = create_data_node("Child shape", PgpEditorMode.CHILD_SHAPE, self.current_particle.child_shape)
            self.treeParticleBlocks.addTopLevelItem(node)

        if self.current_particle.ex_tex_shape:
            node = create_data_node("Indirect shape", PgpEditorMode.EX_TEX_SHAPE, self.current_particle.ex_tex_shape)
            self.treeParticleBlocks.addTopLevelItem(node)

    def select_particle_block(self):
        # Make sure only one block is selected, not 0 or multiple blocks.
        if len(self.treeParticleBlocks.selectedItems()) != 1:
            return

        current_block_node = self.treeParticleBlocks.currentItem()
        current_block_type = current_block_node.data(0, PBNODE_MODE)
        current_block_data = current_block_node.data(0, PBNODE_DATA)
        self.show_particle_settings_tab(6)
        self.keySettings.setEnabled(False)
        self.keyRemove.setEnabled(False)
        self.btnRemoveBlock.setEnabled(False)
        self.hide_all_particle_settings_tabs()
        if current_block_type == PgpEditorMode.DYNAMICS_BLOCK:
            # 0-3: Emitter Tabs
            for i in range(4):
                self.show_particle_settings_tab(i)
            self.emitterTranslationX.setValue(current_block_data.emitter_translation_x.get_val())
            self.emitterTranslationY.setValue(current_block_data.emitter_translation_y.get_val())
            self.emitterTranslationZ.setValue(current_block_data.emitter_translation_z.get_val())
            self.emitterRotationX.setValue(current_block_data.emitter_rotation_x_deg.get_val())
            self.emitterRotationY.setValue(current_block_data.emitter_rotation_y_deg.get_val())
            self.emitterRotationZ.setValue(current_block_data.emitter_rotation_z_deg.get_val())
            self.emitterScaleX.setValue(current_block_data.emitter_scale_x.get_val())
            self.emitterScaleY.setValue(current_block_data.emitter_scale_y.get_val())
            self.emitterScaleZ.setValue(current_block_data.emitter_scale_z.get_val())
            self.emitterDirectionX.setValue(current_block_data.emitter_direction_x.get_val())
            self.emitterDirectionY.setValue(current_block_data.emitter_direction_y.get_val())
            self.emitterDirectionZ.setValue(current_block_data.emitter_direction_z.get_val())
            self.initialVelocityOmni.setValue(current_block_data.initial_velocity_omni.get_val())
            self.initialVelocityRandom.setValue(current_block_data.initial_velocity_random.get_val())
            self.initialVelocityRatio.setValue(current_block_data.initial_velocity_ratio.get_val())
            self.initialVelocityAxis.setValue(current_block_data.initial_velocity_axis.get_val())
            self.initialVelocityDirection.setValue(current_block_data.initial_velocity_direction.get_val())
            self.lifetime.setValue(current_block_data.lifetime.get_val())
            self.startFrame.setValue(current_block_data.start_frame.get_val())
            self.rate.setValue(current_block_data.rate.get_val())
            self.rateStep.setValue(current_block_data.rate_step.get_val())
            self.lifetimeRandom.setValue(current_block_data.lifetime_random.get_val())
            self.maxFrame.setValue(current_block_data.max_frame.get_val())
            self.rateRandom.setValue(current_block_data.rate_random.get_val())
            self.volumeType.setCurrentIndex(current_block_data.flags.get_val_flag_name("VolumeType"))
            self.volumeSweep.setValue(current_block_data.volume_sweep.get_val())
            self.volumeMinRadius.setValue(current_block_data.volume_minimum_radius.get_val())
            self.volumeSize.setValue(current_block_data.volume_size.get_val())
            self.airResistance.setValue(current_block_data.air_resistance.get_val())
            self.momentRandom.setValue(current_block_data.moment_random.get_val())
            self.spread.setValue(current_block_data.spread.get_val())
            self.followEmitter.setChecked(current_block_data.flags.get_val_flag_name("FollowEmitter"))
            self.followEmitterChild.setChecked(current_block_data.flags.get_val_flag_name("FollowEmitterChild"))
            self.fixedDensity.setChecked(current_block_data.flags.get_val_flag_name("FixedDensity"))
            self.fixedInterval.setChecked(current_block_data.flags.get_val_flag_name("FixedInterval"))
            self.inheritScale.setChecked(current_block_data.flags.get_val_flag_name("InheritScale"))
            self.divisionNumber.setValue(current_block_data.division_number.get_val())
        elif current_block_type == PgpEditorMode.FIELD_BLOCK:
            for i in range(4, 6):
                # 4, 5: Field Block
                self.show_particle_settings_tab(i)
            self.btnRemoveBlock.setEnabled(True)
            self.fieldType.setCurrentIndex(current_block_data.flags.get_val_flag_name("FieldType"))
            self.velocityType.setCurrentIndex(current_block_data.flags.get_val_flag_name("VelocityType"))
            self.noInheritRotate.setChecked(current_block_data.flags.get_val_flag_name("NoInheritRotate"))
            self.airDrag.setChecked(current_block_data.flags.get_val_flag_name("AirDrag"))
            self.fadeUseEnterTime.setChecked(current_block_data.flags.get_val_flag_name("FadeUseEnterTime"))
            self.fadeUseDistanceTime.setChecked(current_block_data.flags.get_val_flag_name("FadeUseDistanceTime"))
            self.fadeUseFadeIn.setChecked(current_block_data.flags.get_val_flag_name("FadeUseFadeIn"))
            self.fadeUseFadeOut.setChecked(current_block_data.flags.get_val_flag_name("FadeUseFadeOut"))
            self.positionX.setValue(current_block_data.position_x.get_val())
            self.positionY.setValue(current_block_data.position_y.get_val())
            self.positionZ.setValue(current_block_data.position_z.get_val())
            self.directionX.setValue(current_block_data.direction_x.get_val())
            self.directionY.setValue(current_block_data.direction_y.get_val())
            self.directionZ.setValue(current_block_data.direction_z.get_val())
            self.param1.setValue(current_block_data.param_1.get_val())
            self.param2.setValue(current_block_data.param_2.get_val())
            self.param3.setValue(current_block_data.param_3.get_val())
            self.fadeIn.setValue(current_block_data.fade_in.get_val())
            self.fadeOut.setValue(current_block_data.fade_out.get_val())
            self.enterTime.setValue(current_block_data.enter_time.get_val())
            self.distanceTime.setValue(current_block_data.distance_time.get_val())
            self.cycle.setValue(current_block_data.cycle.get_val())
        elif current_block_type == PgpEditorMode.KEY_BLOCK:
            self.btnRemoveBlock.setEnabled(True)
            self.keyframeTree.clear()
            self.show_particle_settings_tab(6)
            self.keyLoop.setChecked(current_block_data.loop.get_val())
            self.keyType.setCurrentIndex(current_block_data.key_type.get_val())
            for keyframe in current_block_data.keyframes:
                self.put_keyframe(keyframe, False)
        elif current_block_type == PgpEditorMode.BASE_SHAPE:
            for i in range(15, 23):
                self.show_particle_settings_tab(i)
            current_block_data : jsystem.jpac210.JPABaseShape
            self.baseProjectionEnabled.setChecked(current_block_data.flags.get_val_flag_name("IsEnableProjection"))
            self.baseDrawForwardAhead.setChecked(current_block_data.flags.get_val_flag_name("IsDrawForwardAhead"))
            self.baseDrawPrintAhead.setChecked(current_block_data.flags.get_val_flag_name("IsDrawPrintAhead"))
            self.baseTilingS.setCurrentIndex(int(current_block_data.flags.get_val_flag_name("DoubleTilingS")))
            self.baseTilingT.setCurrentIndex(int(current_block_data.flags.get_val_flag_name("DoubleTilingT")))
            self.baseDontDrawParent.setChecked(current_block_data.flags.get_val_flag_name("IsNoDrawParent"))
            self.baseDontDrawChild.setChecked(current_block_data.flags.get_val_flag_name("IsNoDrawChild"))
            self.baseBaseSizeX.setValue(current_block_data.base_size_x.get_val())
            self.baseBaseSizeY.setValue(current_block_data.base_size_y.get_val())
            self.baseBlendMode.setCurrentIndex(current_block_data.blend_mode_flags.get_val_flag_name("BlendMode"))
            self.baseBlendSourceFactor.setCurrentIndex(current_block_data.blend_mode_flags.get_val_flag_name("SourceFactor"))
            self.baseBlendDestinationFactor.setCurrentIndex(current_block_data.blend_mode_flags.get_val_flag_name("DestinationFactor"))
            self.baseDepthTest.setChecked(current_block_data.z_mode_flags.get_val_flag_name("DepthTest"))
            self.baseDepthCompareType.setCurrentIndex(current_block_data.z_mode_flags.get_val_flag_name("DepthCompareType"))
            self.baseDepthWrite.setChecked(current_block_data.z_mode_flags.get_val_flag_name("DepthWrite"))
            self.baseShapeType.setCurrentIndex(current_block_data.flags.get_val_flag_name("ShapeType"))
            self.baseDirectionType.setCurrentIndex(current_block_data.flags.get_val_flag_name("DirectionType"))
            self.baseRotationType.setCurrentIndex(current_block_data.flags.get_val_flag_name("RotationType"))
            self.basePlaneType.setCurrentIndex(current_block_data.flags.get_val_flag_name("PlaneType"))
            self.baseAlphaCompareType0.setCurrentIndex(current_block_data.alpha_compare_flags.get_val_flag_name("AlphaCompareType0"))
            self.baseAlphaCompareType1.setCurrentIndex(current_block_data.alpha_compare_flags.get_val_flag_name("AlphaCompareType1"))
            self.baseAlphaOperator.setCurrentIndex(current_block_data.alpha_compare_flags.get_val_flag_name("AlphaOperator"))
            self.baseAlphaReference0.setValue(current_block_data.alpha_reference_0.get_val())
            self.baseAlphaReference1.setValue(current_block_data.alpha_reference_1.get_val())
            self.baseAlphaInSelect.setValue(current_block_data.flags.get_val_flag_name("AlphaInSelect"))
            self.baseGlobalTextureAnimation.setChecked(current_block_data.flags.get_val_flag_name("IsGlobalTextureAnimation"))
            self.baseTextureCalculateIndexType.setCurrentIndex(current_block_data.texture_flags.get_val_flag_name("TexCalcIndexType"))
            self.baseTextureIndex.setValue(current_block_data.texture_index.get_val())
            is_enabled_tex = current_block_data.texture_flags.get_val_flag_name("IsEnableTexAnim")
            self.baseEnableTextureAnimation.setChecked(is_enabled_tex)
            self.baseTextureIndexWidget.setEnabled(is_enabled_tex)
            self.baseTextureIndexDelete.setEnabled(False)
            self.baseTextureIndexData.clear()
            for x in current_block_data.texture_index_anim_data:
                self.put_texture_index(x, False)
            self.baseColorCalculateIndexType.setCurrentIndex(current_block_data.color_flags.get_val_flag_name("ColorCalcIndexType"))
            self.basePrimaryColor.setText(str(current_block_data.primary_color.get_val().hex()))
            self.baseEnvironmentColor.setText(str(current_block_data.environment_color.get_val().hex()))
            self.baseColorLoopOffsetMask.setValue(current_block_data.color_loop_offset_mask.get_val())
            self.baseColorInSelect.setValue(current_block_data.flags.get_val_flag_name("ColorInSelect"))
            self.baseColorAnimationMaxFrame.setValue(current_block_data.color_animation_max_frame.get_val())
            self.baseGlobalColorAnimation.setChecked(current_block_data.flags.get_val_flag_name("IsGlobalColorAnimation"))
            self.baseAnimationRandom.setValue(current_block_data.animation_random.get_val())
            is_enabled_tex_scroll = current_block_data.flags.get_val_flag_name("IsEnableTexScrollAnim")
            self.baseTextureScrollAnimEnabled.setChecked(is_enabled_tex_scroll)
            self.baseTextureScrollAnimWidget.setEnabled(is_enabled_tex_scroll)
            self.baseIndexLoopOffsetMask.setValue(current_block_data.texture_index_loop_offset_mask.get_val())
            self.baseInitialTranslationX.setValue(current_block_data.tex_init_trans_x.get_val())
            self.baseInitialTranslationY.setValue(current_block_data.tex_init_trans_y.get_val())
            self.baseInitialScaleX.setValue(current_block_data.tex_init_scale_x.get_val())
            self.baseInitialScaleY.setValue(current_block_data.tex_init_scale_y.get_val())
            self.baseInitialRotation.setValue(current_block_data.tex_init_rot.get_val())
            self.baseIncrementRotation.setValue(current_block_data.tex_inc_rot.get_val())
            self.baseIncrementTranslationX.setValue(current_block_data.tex_inc_trans_x.get_val())
            self.baseIncrementTranslationY.setValue(current_block_data.tex_inc_trans_y.get_val())
            self.baseIncrementScaleX.setValue(current_block_data.tex_inc_scale_x.get_val())
            self.baseIncrementScaleY.setValue(current_block_data.tex_inc_scale_y.get_val())
            # do primary color anim stuff
            is_primary_enabled = current_block_data.color_flags.get_val_flag_name("IsPrimaryColorAnimEnabled")
            self.basePrimaryColorTree.clear()
            self.basePrimaryColorLeft.setEnabled(is_primary_enabled)
            self.set_primary_color_frame_enabled(False)
            for primary_color in current_block_data.primary_color_data:
                self.put_color_frame(primary_color, self.basePrimaryColorTree, False)
            self.basePrimaryColorAnimEnabled.setChecked(is_primary_enabled)
            # do env color anim stuff
            is_env_enabled = current_block_data.color_flags.get_val_flag_name("IsEnvironmentColorAnimEnabled")
            self.baseEnvironmentColorTree.clear()
            self.baseEnvironmentColorLeft.setEnabled(is_env_enabled)
            self.set_environment_color_frame_enabled(False)
            for color in current_block_data.environment_color_data:
                self.put_color_frame(color, self.baseEnvironmentColorTree, False)
            self.baseEnvironmentColorAnimEnabled.setChecked(is_env_enabled)

        elif current_block_type == PgpEditorMode.EXTRA_SHAPE:
            for i in range(11, 15):
                self.show_particle_settings_tab(i)
            self.btnRemoveBlock.setEnabled(True)
            self.extraIsDiffXY.setChecked(current_block_data.flags.get_val_flag_name("IsDiffXY"))
            self.extraSinWaveEnabled.setChecked(current_block_data.flags.get_val_flag_name("IsEnableSinWave"))
            self.extraPivotX.setValue(current_block_data.flags.get_val_flag_name("PivotX"))
            self.extraPivotY.setValue(current_block_data.flags.get_val_flag_name("PivotY"))
            self.extraScaleEnabled.setChecked(current_block_data.flags.get_val_flag_name("IsEnableScale"))
            self.extraScaleInTiming.setValue(current_block_data.scale_in_timing.get_val())
            self.extraScaleInValueX.setValue(current_block_data.scale_in_value_x.get_val())
            self.extraScaleInValueY.setValue(current_block_data.scale_in_value_y.get_val())
            self.extraScaleAnimXMaxFrame.setValue(current_block_data.scale_animation_x_max_frame.get_val())
            self.extraScaleAnimTypeX.setCurrentIndex(current_block_data.flags.get_val_flag_name("ScaleAnimTypeX"))
            self.extraScaleOutRandom.setValue(current_block_data.scale_out_random.get_val())
            self.extraScaleOutTiming.setValue(current_block_data.scale_out_timing.get_val())
            self.extraScaleOutValueX.setValue(current_block_data.scale_out_value_x.get_val())
            self.extraScaleOutValueY.setValue(current_block_data.scale_out_value_y.get_val())
            self.extraScaleAnimYMaxFrame.setValue(current_block_data.scale_animation_y_max_frame.get_val())
            self.extraScaleAnimTypeY.setCurrentIndex(current_block_data.flags.get_val_flag_name("ScaleAnimTypeY"))
            self.extraAlphaEnabled.setChecked(current_block_data.flags.get_val_flag_name("IsEnableAlpha"))
            self.extraAlphaInTiming.setValue(current_block_data.alpha_in_timing.get_val())
            self.extraAlphaInValue.setValue(current_block_data.alpha_in_value.get_val())
            self.extraAlphaBaseValue.setValue(current_block_data.alpha_base_value.get_val())
            self.extraAlphaWaveRandom.setValue(current_block_data.alpha_wave_random.get_val())
            self.extraAlphaOutTiming.setValue(current_block_data.alpha_out_timing.get_val())
            self.extraAlphaOutValue.setValue(current_block_data.alpha_out_value.get_val())
            self.extraAlphaWaveFrequency.setValue(current_block_data.alpha_wave_frequency.get_val())
            self.extraAlphaWaveAmplitude.setValue(current_block_data.alpha_wave_amplitude.get_val())
            self.extraRotationEnabled.setChecked(current_block_data.flags.get_val_flag_name("IsEnableRotate"))
            self.extraRotationAngle.setValue(current_block_data.rotate_angle.get_val())
            self.extraRotationSpeed.setValue(current_block_data.rotate_speed.get_val())
            self.extraRotationDirection.setValue(current_block_data.rotate_direction.get_val())
            self.extraRotationAngleRandom.setValue(current_block_data.rotate_angle_random.get_val())
            self.extraRotationSpeedRandom.setValue(current_block_data.rotate_speed_random.get_val())
                
        elif current_block_type == PgpEditorMode.CHILD_SHAPE:
            for i in range(8, 11):
                self.show_particle_settings_tab(i)
            self.btnRemoveBlock.setEnabled(True)
            self.childShapeType.setCurrentIndex(current_block_data.flags.get_val_flag_name("ShapeType"))
            self.childRotationType.setCurrentIndex(current_block_data.flags.get_val_flag_name("RotationType"))
            self.childDirectionType.setCurrentIndex(current_block_data.flags.get_val_flag_name("DirectionType"))
            self.childPlaneType.setCurrentIndex(current_block_data.flags.get_val_flag_name("PlaneType"))
            self.childFieldEnabled.setChecked(current_block_data.flags.get_val_flag_name("IsEnableField"))
            self.childScaleOutEnabled.setChecked(current_block_data.flags.get_val_flag_name("IsEnableScaleOut"))
            self.childAlphaOutEnabled.setChecked(current_block_data.flags.get_val_flag_name("IsEnableAlphaOut"))
            self.childRotationEnabled.setChecked(current_block_data.flags.get_val_flag_name("IsEnableRotate"))
            self.childGlobalScale2DX.setValue(current_block_data.global_scale_2d_x.get_val())
            self.childGlobalScale2DY.setValue(current_block_data.global_scale_2d_y.get_val())
            self.childPrimaryColor.setText(str(current_block_data.primary_color.get_val().hex()))
            self.childEnvironmentColor.setText(str(current_block_data.environment_color.get_val().hex()))
            self.childTextureIndex.setValue(current_block_data.texture_index.get_val())
            self.childScaleInherited.setChecked(current_block_data.flags.get_val_flag_name("IsInheritedScale"))
            self.childInheritScale.setValue(current_block_data.inherit_scale.get_val())
            self.childAlphaInherited.setChecked(current_block_data.flags.get_val_flag_name("IsInheritedAlpha"))
            self.childInheritAlpha.setValue(current_block_data.inherit_alpha.get_val())
            self.childRGBInherited.setChecked(current_block_data.flags.get_val_flag_name("IsInheritedRGB"))
            self.childInheritRGB.setValue(current_block_data.inherit_rgb.get_val())
            self.childTiming.setValue(current_block_data.timing.get_val())
            self.childLife.setValue(current_block_data.life.get_val())
            self.childRate.setValue(current_block_data.rate.get_val())
            self.childStep.setValue(current_block_data.step.get_val())
            self.childRotateSpeed.setValue(current_block_data.rotate_speed.get_val())
            self.childVelocityInfluenceRate.setValue(current_block_data.velocity_influence_rate.get_val())
            self.childBaseVelocity.setValue(current_block_data.base_velocity.get_val())
            self.childBaseVelocityRandom.setValue(current_block_data.base_velocity_random.get_val())
            self.childGravity.setValue(current_block_data.gravity.get_val())
            self.childPositionRandom.setValue(current_block_data.position_random.get_val())
        elif current_block_type == PgpEditorMode.EX_TEX_SHAPE:
            self.show_particle_settings_tab(7)
            self.btnRemoveBlock.setEnabled(True)
            self.indirectTextureMode.setCurrentIndex(self.current_particle.ex_tex_shape.flags.get_val_flag_name("IndirectTextureMode"))
            self.matrixScale.setValue(self.current_particle.ex_tex_shape.matrix_scale.get_val())
            self.indirectTextureIndex.setValue(self.current_particle.ex_tex_shape.indirect_texture_index.get_val())
            self.useSecondTextureIndex.setChecked(self.current_particle.ex_tex_shape.flags.get_val_flag_name("UseSecondTextureIndex"))
            self.secondTextureIndex.setValue(self.current_particle.ex_tex_shape.second_texture_index.get_val())
            self.indirectTexMatrix00.setValue(self.current_particle.ex_tex_shape.indirect_texture_matrix_0_0.get_val())
            self.indirectTexMatrix01.setValue(self.current_particle.ex_tex_shape.indirect_texture_matrix_0_1.get_val())
            self.indirectTexMatrix02.setValue(self.current_particle.ex_tex_shape.indirect_texture_matrix_0_2.get_val())
            self.indirectTexMatrix10.setValue(self.current_particle.ex_tex_shape.indirect_texture_matrix_1_0.get_val())
            self.indirectTexMatrix11.setValue(self.current_particle.ex_tex_shape.indirect_texture_matrix_1_1.get_val())
            self.indirectTexMatrix12.setValue(self.current_particle.ex_tex_shape.indirect_texture_matrix_1_2.get_val())
        
    def texture_index_changed(self, item):
        i = self.baseTextureIndexData.indexOfTopLevelItem(item)
        try:
            value = int(item.text(0))
            if value > 255:
                value = 255
                item.setText(0, "255")
            elif value < 0:
                value = 0
                item.setText(0, "0")
            self.get_current_block_data().texture_index_anim_data[i] = value
        except ValueError:
            item.setText(0, "0")
    
    def enable_texture_animation(self, val):
        self.get_current_block_data().texture_flags.set_val_flag_name("IsEnableTexAnim", val)
        self.baseTextureIndexWidget.setEnabled(val)

    def selection_changed_texture_animation(self):
        if len(self.baseTextureIndexData.selectedItems()) != 1:
            self.baseTextureIndexDelete.setEnabled(False)
            return
        self.baseTextureIndexDelete.setEnabled(True)
    
    def remove_selected_texture_index(self):
        current_node = self.baseTextureIndexData.currentItem()
        index = self.baseTextureIndexData.indexOfTopLevelItem(current_node)
        del self.get_current_block_data().texture_index_anim_data[index]
        self.baseTextureIndexData.takeTopLevelItem(index)  

    def put_texture_index(self, x, select=True):
        node = QtWidgets.QTreeWidgetItem([str(x)])
        node.setFlags(node.flags() | QtCore.Qt.ItemFlag.ItemIsEditable)
        node.setData(0, PBNODE_DATA, x)
        self.baseTextureIndexData.addTopLevelItem(node)
        if select:
            self.baseTextureIndexData.setCurrentItem(node)

    def add_texture_index(self):
        self.put_texture_index(0)
        self.get_current_block_data().texture_index_anim_data.append(0)

    def enable_texture_scroll_anim(self, val):
        self.get_current_block_data().flags.set_val_flag_name("IsEnableTexScrollAnim", val)
        self.baseTextureScrollAnimEnabled.setChecked(val)
        self.baseTextureScrollAnimWidget.setEnabled(val)
    
    def select_keyframe(self):
        if len(self.keyframeTree.selectedItems()) != 1:
            self.keySettings.setEnabled(False)
            self.keyRemove.setEnabled(False)
            return
        current_key_node = self.keyframeTree.currentItem()
        if not current_key_node:
            return
        current_key_data = current_key_node.data(0, PBNODE_DATA)
        self.keySettings.setEnabled(True)
        self.keyRemove.setEnabled(True)
        self.keyTime.setValue(current_key_data.time.get_val())
        self.keyValue.setValue(current_key_data.value.get_val())
        self.keyTangentIn.setValue(current_key_data.tan_in.get_val())
        self.keyTangentOut.setValue(current_key_data.tan_out.get_val())
    
    def set_keyframe_data(self, name, val):
        current_key_node = self.keyframeTree.currentItem()
        current_key_data = current_key_node.data(0, PBNODE_DATA)
        if name == "Time":
            current_key_node.setText(0, "Time " + str(round(val, 4)))
            current_key_data.time.set_val(val)
        elif name == "Value":
            current_key_data.value.set_val(val)
        elif name == "TangentIn":
            current_key_data.tan_in.set_val(val)
        elif name == "TangentOut":
            current_key_data.tan_out.set_val(val)
    
    def remove_selected_keyframe(self):
        current_tree_node = self.treeParticleBlocks.currentItem()
        current_tree_data = current_tree_node.data(0, PBNODE_DATA)
        current_key_node = self.keyframeTree.currentItem()
        current_key_data = current_key_node.data(0, PBNODE_DATA)
        index = self.keyframeTree.indexOfTopLevelItem(current_key_node)
        current_tree_data.keyframes.remove(current_key_data)
        self.keyframeTree.takeTopLevelItem(index)  
    
    def put_keyframe(self, keyframe, select=True):
        name = "Time " + str(round(keyframe.time.get_val(), 4))
        node = QtWidgets.QTreeWidgetItem([name])
        node.setData(0, PBNODE_DATA, keyframe)
        self.keyframeTree.addTopLevelItem(node)
        if select:
            self.keyframeTree.setCurrentItem(node)
    
    def add_keyframe(self):
        current_tree_node = self.treeParticleBlocks.currentItem()
        current_tree_data = current_tree_node.data(0, PBNODE_DATA)
        keyframe = jsystem.jpac210.JPAKeyframe()
        current_tree_data.keyframes.append(keyframe)
        self.put_keyframe(keyframe)
    
    def get_color_tree_data(self, tree):
        current_tree_node = self.treeParticleBlocks.currentItem()
        current_tree_data = current_tree_node.data(0, PBNODE_DATA) 
        current_tree_data : jsystem.jpac210.JPABaseShape
        if tree == self.basePrimaryColorTree:
            return current_tree_data.primary_color_data
        elif tree == self.baseEnvironmentColorTree:
            return current_tree_data.environment_color_data

    def remove_selected_color_frame(self, tree):
        current_key_node = tree.currentItem()
        current_key_data = current_key_node.data(0, PBNODE_DATA)
        index = tree.indexOfTopLevelItem(current_key_node)
        self.get_color_tree_data(tree).remove(current_key_data)
        tree.takeTopLevelItem(index)  
    
    def put_color_frame(self, frame, tree, select=True):
        name = "Frame " + str(round(frame.frame.get_val(), 4))
        node = QtWidgets.QTreeWidgetItem([name])
        node.setData(0, PBNODE_DATA, frame)
        tree.addTopLevelItem(node)
        if select:
            tree.setCurrentItem(node)
    
    def add_color_frame(self, tree):
        frame = jsystem.jpac210.JPAColorFrame()
        self.get_color_tree_data(tree).append(frame)
        self.put_color_frame(frame, tree)

    def set_color_frame_data(self, name, val, tree):
        current_frame_node = tree.currentItem()
        current_frame_data = current_frame_node.data(0, PBNODE_DATA)
        if name == "Frame":
            current_frame_node.setText(0, "Frame " + str(round(val, 4)))
            current_frame_data.frame.set_val(val)
        elif name == "Color":
            current_frame_data.color.set_val(val)

    def set_primary_color_frame_enabled(self, enabled):
        self.basePrimaryColorDelete.setEnabled(enabled)
        self.basePrimaryColorRight.setEnabled(enabled)
    
    def set_primary_color_enabled(self, val):
        if len(self.basePrimaryColorTree.selectedItems()) == 1 and val == True:
            self.basePrimaryColorRight.setEnabled(True)
        else:
            self.basePrimaryColorRight.setEnabled(False)
        self.basePrimaryColorLeft.setEnabled(val)
        self.get_current_block_data().color_flags.set_val_flag_name("IsPrimaryColorAnimEnabled", val)

    def select_primary_color_frame(self):
        if len(self.basePrimaryColorTree.selectedItems()) != 1:
            self.set_primary_color_frame_enabled(False)
            return
        
        current_key_node = self.basePrimaryColorTree.currentItem()
        if not current_key_node:
            return
        current_frame_data = current_key_node.data(0, PBNODE_DATA)
        if self.get_current_block_data().color_flags.get_val_flag_name("IsPrimaryColorAnimEnabled") == False:
            self.set_primary_color_frame_enabled(False)
            return
        self.set_primary_color_frame_enabled(True)
        self.basePrimaryColorFrame.setValue(current_frame_data.frame.get_val())
        self.basePrimaryColorColor.setText(str(current_frame_data.color.get_val().hex()))
    
    def set_environment_color_frame_enabled(self, enabled):
        self.baseEnvironmentColorDelete.setEnabled(enabled)
        self.baseEnvironmentColorRight.setEnabled(enabled)
    
    def set_environment_color_enabled(self, val):
        if len(self.baseEnvironmentColorTree.selectedItems()) == 1 and val == True:
            self.baseEnvironmentColorRight.setEnabled(True)
        else:
            self.baseEnvironmentColorRight.setEnabled(False)
        self.baseEnvironmentColorLeft.setEnabled(val)
        self.get_current_block_data().color_flags.set_val_flag_name("IsEnvironmentColorAnimEnabled", val)

    def select_environment_color_frame(self):
        if len(self.baseEnvironmentColorTree.selectedItems()) != 1:
            self.set_environment_color_frame_enabled(False)
            return
        
        current_key_node = self.baseEnvironmentColorTree.currentItem()
        if not current_key_node:
            return
        current_frame_data = current_key_node.data(0, PBNODE_DATA)
        if self.get_current_block_data().color_flags.get_val_flag_name("IsEnvironmentColorAnimEnabled") == False:
            self.set_environment_color_frame_enabled(False)
            return
        self.set_environment_color_frame_enabled(True)
        self.baseEnvironmentColorFrame.setValue(current_frame_data.frame.get_val())
        self.baseEnvironmentColorColor.setText(str(current_frame_data.color.get_val().hex()))
    
    def get_current_field_block(self):
        current_item = self.treeParticleBlocks.currentItem()
        if current_item.data(0, PBNODE_MODE) == PgpEditorMode.FIELD_BLOCK:
            return current_item.data(0, PBNODE_DATA)
        else:
            return None
    
    def get_current_key_block(self):
        current_item = self.treeParticleBlocks.currentItem()
        if current_item.data(0, PBNODE_MODE) == PgpEditorMode.KEY_BLOCK:
            return current_item.data(0, PBNODE_DATA)
        else:
            return None
        
    def get_current_block_data(self):
        current_item = self.treeParticleBlocks.currentItem()
        return current_item.data(0, PBNODE_DATA)
    
    def show_add_block_menu(self):
        add_block_menu = QtWidgets.QMenu("Add block", self)
        field_action = QtWidgets.QAction("Field block", self)
        field_action.triggered.connect(lambda: self.add_particle_block(PgpEditorMode.FIELD_BLOCK))
        add_block_menu.addAction(field_action)
        key_action = QtWidgets.QAction("Key block", self)
        key_action.triggered.connect(lambda: self.add_particle_block(PgpEditorMode.KEY_BLOCK))
        add_block_menu.addAction(key_action)
        if not self.current_particle.extra_shape:
            extra_action = QtWidgets.QAction("Extra shape", self)
            extra_action.triggered.connect(lambda: self.add_particle_block(PgpEditorMode.EXTRA_SHAPE))
            add_block_menu.addAction(extra_action)
        if not self.current_particle.child_shape:
            child_action = QtWidgets.QAction("Child shape", self)
            child_action.triggered.connect(lambda: self.add_particle_block(PgpEditorMode.CHILD_SHAPE))
            add_block_menu.addAction(child_action)
        if not self.current_particle.ex_tex_shape:
            ex_tex_action = QtWidgets.QAction("Indirect shape", self)
            ex_tex_action.triggered.connect(lambda: self.add_particle_block(PgpEditorMode.EX_TEX_SHAPE))
            add_block_menu.addAction(ex_tex_action)
        add_block_menu.exec_(self.btnAddBlock.mapToGlobal(self.btnAddBlock.rect().bottomLeft()))
    
    def add_particle_block(self, block_type : PgpEditorMode):
        if self.get_editor_mode() != PgpEditorMode.PARTICLE:
            return
        if len(self.listParticles.selectedItems()) == 0:
            self.status("No particle(s) selected!", StatusColor.ERROR)
            return
        if block_type == PgpEditorMode.FIELD_BLOCK:
            self.current_particle : jsystem.jpac210.JPAResource
            new_block = jsystem.jpac210.JPAFieldBlock()
            self.current_particle.field_blocks.append(new_block)
            if self.current_particle.field_blocks is None:
                self.current_particle.field_blocks = list()
            node = self.find_particle_block(PgpEditorMode.FIELD_BLOCKS)
            block_node = create_data_node("Field block", PgpEditorMode.FIELD_BLOCK, new_block)
            node.addChild(block_node)
        elif block_type == PgpEditorMode.KEY_BLOCK:
            self.current_particle : jsystem.jpac210.JPAResource
            new_block = jsystem.jpac210.JPAKeyBlock()
            self.current_particle.key_blocks.append(new_block)
            if self.current_particle.key_blocks is None:
                self.current_particle.key_blocks = list()
            node = self.find_particle_block(PgpEditorMode.KEY_BLOCKS)
            block_node = create_data_node("Key block", PgpEditorMode.KEY_BLOCK, new_block)
            node.addChild(block_node)
        elif block_type == PgpEditorMode.EXTRA_SHAPE:
            # if there's already an extra shape, return
            if self.current_particle.extra_shape:
                return
            self.current_particle.extra_shape = jsystem.jpac210.JPAExtraShape()
            block_node = create_data_node("Extra shape", PgpEditorMode.EXTRA_SHAPE, self.current_particle.extra_shape)
            self.treeParticleBlocks.addTopLevelItem(block_node)
        elif block_type == PgpEditorMode.CHILD_SHAPE:
            # if there's already a child shape, return
            if self.current_particle.child_shape:
                return
            self.current_particle.child_shape = jsystem.jpac210.JPAChildShape()
            block_node = create_data_node("Child shape", PgpEditorMode.CHILD_SHAPE, self.current_particle.child_shape)
            self.treeParticleBlocks.addTopLevelItem(block_node)
        elif block_type == PgpEditorMode.EX_TEX_SHAPE:
            # if there's already an indirect shape, return
            if self.current_particle.ex_tex_shape:
                return
            self.current_particle.ex_tex_shape = jsystem.jpac210.JPAExTexShape()
            block_node = create_data_node("Indirect shape", PgpEditorMode.EX_TEX_SHAPE, self.current_particle.ex_tex_shape)
            self.treeParticleBlocks.addTopLevelItem(block_node)
        else:
            self.status("Can't add block of type " + block_type.name + ". Unrecognized type.", StatusColor.ERROR)
            return
        self.status("Added new block.", StatusColor.INFO)

    def find_particle_block(self, block_type : PgpEditorMode):
        for i in range(self.treeParticleBlocks.topLevelItemCount()):
            node = self.treeParticleBlocks.topLevelItem(i)
            mode = node.data(0, PBNODE_MODE)
            if mode == block_type:
                return node
        return None
    
    def remove_selected_particle_block(self):
        # Make sure only one block is selected, not 0 or multiple blocks.
        if len(self.treeParticleBlocks.selectedItems()) != 1:
            return

        block_node = self.treeParticleBlocks.currentItem()
        mode = block_node.data(0, PBNODE_MODE)
        
        if mode == PgpEditorMode.FIELD_BLOCK:
            top_level_node = self.find_particle_block(PgpEditorMode.FIELD_BLOCKS)
            index = top_level_node.indexOfChild(block_node)
            top_level_node.takeChild(index)
            del self.current_particle.field_blocks[index]
        elif mode == PgpEditorMode.KEY_BLOCK:
            top_level_node = self.find_particle_block(PgpEditorMode.KEY_BLOCKS)
            index = top_level_node.indexOfChild(block_node)
            top_level_node.takeChild(index)
            del self.current_particle.key_blocks[index]
        elif mode == PgpEditorMode.CHILD_SHAPE: 
            self.treeParticleBlocks.takeTopLevelItem(self.treeParticleBlocks.indexOfTopLevelItem(block_node))
            self.current_particle.child_shape = None
        elif mode == PgpEditorMode.EXTRA_SHAPE:
            self.treeParticleBlocks.takeTopLevelItem(self.treeParticleBlocks.indexOfTopLevelItem(block_node))
            self.current_particle.extra_shape = None
        elif mode == PgpEditorMode.EX_TEX_SHAPE:
            self.treeParticleBlocks.takeTopLevelItem(self.treeParticleBlocks.indexOfTopLevelItem(block_node))
            self.current_particle.ex_tex_shape = None
        else:
            self.status("Can't remove block of type " + mode.name + ". Not removable.", StatusColor.ERROR)
    
    def hide_all_particle_settings_tabs(self):
        for i in range(self.particleSettingsTabs.count()):
            self.particleSettingsTabs.setTabVisible(i, False)
            self.particleSettingsTabs.setTabEnabled(i, False)
    
    def show_particle_settings_tab(self, index):
        self.particleSettingsTabs.setTabVisible(index, True)
        self.particleSettingsTabs.setTabEnabled(index, True)

    def add_particle(self):
        if self.get_editor_mode() != PgpEditorMode.PARTICLE:
            return
        # Make sure the added particle is selected afterwards
        new_index = self.listParticles.count()

        # Create new particle
        new_particle = jsystem.jpac210.JPAResource()
        name = "NewParticle" + str(new_index)
        new_particle.name = name
        self.particle_data.particles.append(new_particle)
        self.listParticles.addItem(name)

        # Update list selection
        self.listParticles.clearSelection()
        self.listParticles.setCurrentRow(new_index)

        self.status("Added a new particle.", StatusColor.INFO)

    def delete_particles(self):
        if self.get_editor_mode() != PgpEditorMode.PARTICLE:
            return
        if len(self.listParticles.selectedItems()) == 0:
            self.status("No particle(s) selected!", StatusColor.ERROR)
            return

        # Get selected list indexes
        delete_indexes = [i.row() for i in self.listParticles.selectionModel().selectedIndexes()]

        # The selected indexes are shuffled, so we remove particles starting from the end of the list
        delete_indexes.sort(reverse=True)

        # Go through indexes and delete list item and the actual particle
        for delete_index in delete_indexes:
            self.listParticles.takeItem(delete_index)
            self.particle_data.particles.pop(delete_index)

        self.status(f"Deleted {len(delete_indexes)} particle(s).", StatusColor.INFO)

    def clone_particles(self):
        if self.get_editor_mode() != PgpEditorMode.PARTICLE:
            return
        if len(self.listParticles.selectedItems()) == 0:
            self.status("No particle(s) selected!", StatusColor.ERROR)
            return

        # Get selected list indexes and sort them by original order
        clone_indexes = [i.row() for i in self.listParticles.selectionModel().selectedIndexes()]
        clone_indexes.sort()

        # Make sure the first clone is selected afterwards
        new_index = self.listParticles.count()

        # Create deep clones of all effects and populate them to the respective lists
        for clone_index in clone_indexes:
            clone = copy.deepcopy(self.particle_data.particles[clone_index])
            self.particle_data.particles.append(clone)
            self.listParticles.addItem(clone.name)

        # Update list selection
        self.listParticles.clearSelection()
        self.listParticles.setCurrentRow(new_index)

        self.status(f"Cloned {len(clone_indexes)} particle(s).", StatusColor.INFO)

    def copy_particle(self):
        if self.get_editor_mode() != PgpEditorMode.PARTICLE:
            return
        if self.current_particle is None:
            self.status("No particle selected!", StatusColor.ERROR)
            return

        self.copied_particle = copy.deepcopy(self.particle_data.particles[self.listParticles.currentRow()])

        self.status(f"Copied particle {self.copied_particle.name}.", StatusColor.INFO)

    def replace_particle(self):
        if self.get_editor_mode() != PgpEditorMode.PARTICLE:
            return

        if self.current_particle is None:
            self.status("No particle selected!", StatusColor.ERROR)
            return
        if self.copied_particle is None:
            self.status("No particle copy available!", StatusColor.ERROR)
            return

        # Replace current effect, we want to preserve references to current effect and its members
        old_description = self.current_particle.name
        self.current_particle.replace_with(self.copied_particle)

        # Update widgets and list
        self.select_particle()
        self.update_current_particle_list_item()

        self.status(f"Replaced particle {old_description} with {self.copied_particle.name}.", StatusColor.INFO)

    def export_particles(self):
        if self.get_editor_mode() != PgpEditorMode.PARTICLE:
            return
        if len(self.listParticles.selectedItems()) == 0:
            self.status("No particle(s) selected!", StatusColor.ERROR)
            return

        export_folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Export particles to...")
        if len(export_folder) == 0:
            return

        particle_indexes = [i.row() for i in self.listParticles.selectionModel().selectedIndexes()]
        particle_indexes.sort()

        for particle_index in particle_indexes:
            particle = self.particle_data.particles[particle_index]
            fp_out_particle = os.path.join(export_folder, f"{particle.name}.json")
            pyaurum.write_json_file(fp_out_particle, particle.pack_json())

        self.status(f"Exported {len(particle_indexes)} particle(s) to \"{export_folder}\".", StatusColor.INFO)

    def import_particles(self):
        if self.get_editor_mode() != PgpEditorMode.PARTICLE:
            return

        # Get selected JSON files
        import_files = QtWidgets.QFileDialog.getOpenFileNames(self, "Import from JSON files...", filter="JSON file (*.json)")[0]
        new_particle_count = len(import_files)

        if new_particle_count == 0:
            return

        # Select the first imported entry if no existing particles are replaced
        new_index = self.listParticles.count()

        # We only need to check existing entries for replacement
        old_particle_count = len(self.particle_data.particles)
        replaced_entries = 0

        # Go through all particle JSON files
        for import_file in import_files:
            particle = jsystem.JPAResource()
            particle.name = pyaurum.get_filename(import_file)
            is_new_entry = True

            # Try to read data from JSON file
            try:
                particle.unpack_json(pyaurum.read_json_file(import_file))
            except Exception as e:
                # todo: better exception handling?
                self.show_critical(f"An error occured when importing from \"{import_file}\". See output for details.")
                print(e)
                new_particle_count -= 1
                continue

            # Check if particle has to be replaced
            for particle_index in range(old_particle_count):
                existing_particle = self.particle_data.particles[particle_index]

                if existing_particle.name == particle.name:
                    self.particle_data.particles[particle_index].replace_with(particle)

                    new_index = particle_index  # Select last replaced particle
                    replaced_entries += 1
                    is_new_entry = False
                    break

            # Convert JSON entries to effects and add them to the respective lists
            if is_new_entry:
                self.particle_data.particles.append(particle)
                self.listParticles.addItem(particle.name)

        # Update effects list
        self.listParticles.clearSelection()
        self.listParticles.setCurrentRow(new_index)

        self.status(f"Imported {new_particle_count} particle(s), replaced {replaced_entries} existing particle(s).", StatusColor.INFO)

    def update_current_particle_list_item(self):
        self.listParticles.selectedItems()[0].setText(self.current_particle.name)

    def set_particle_name(self, text: str):
        self.current_particle.name = text
        self.update_current_particle_list_item()
    def set_particle_volume_type(self, val):
        self.current_particle.dynamics_block.flags.set_val_flag_name("VolumeType", val)
    def set_particle_follow_emitter(self, val: bool):
        self.current_particle.dynamics_block.flags.set_val_flag_name("FollowEmitter", val)
    def set_particle_follow_emitter_child(self, val: bool):
        self.current_particle.dynamics_block.flags.set_val_flag_name("FollowEmitterChild", val)
    def set_particle_fixed_density(self, val: bool):
        self.current_particle.dynamics_block.flags.set_val_flag_name("FixedDensity", val)
    def set_particle_fixed_interval(self, val: bool):
        self.current_particle.dynamics_block.flags.set_val_flag_name("FixedInterval", val)
    def set_particle_inherit_scale(self, val: bool):
        self.current_particle.dynamics_block.flags.set_val_flag_name("InheritScale", val)

    # ---------------------------------------------------------------------------------------------
    # Texture editing
    # ---------------------------------------------------------------------------------------------
    def select_texture(self):
        # Make sure only one texture is selected
        if len(self.listTextures.selectedItems()) != 1:
            # self.widgetTextures.setEnabled(False)
            self.current_texture = None
            return

        # Enable all effect editing components and get currently selected effect instance
        # self.widgetTextures.setEnabled(True)
        self.current_texture = self.particle_data.textures[self.listTextures.currentItem().text()]

    def add_or_import_textures(self):
        if self.get_editor_mode() != PgpEditorMode.TEXTURE:
            return

        # Get selected JSON files
        import_files = QtWidgets.QFileDialog.getOpenFileNames(self, "Import BTI files...", filter="BTI file (*.bti)")[0]
        new_texture_count = len(import_files)

        if new_texture_count == 0:
            return

        # Select the first imported entry if no existing particles are replaced
        new_index = self.listTextures.count()
        replaced_entries = 0

        # Go through all BTI files
        for import_file in import_files:
            texture = jsystem.JPATexture()
            texture.file_name = pyaurum.get_filename(import_file)
            is_new_entry = True

            # Try to read data from BTI file
            try:
                texture.bti_data = pyaurum.read_bin_file(import_file)
            except Exception as e:
                # todo: better exception handling?
                self.show_critical(f"An error occured when importing from \"{import_file}\". See output for details.")
                print(e)
                new_texture_count -= 1
                continue

            # Check if texture has to be replaced
            if texture.file_name in self.particle_data.textures:
                existing_texture = self.particle_data.textures[texture.file_name]
                existing_texture.bti_data = texture.bti_data

                new_index = list(self.particle_data.textures.keys()).index(texture.file_name)
                replaced_entries += 1
                is_new_entry = False

            # Add texture to the respective lists
            if is_new_entry:
                self.particle_data.textures[texture.file_name] = texture
                self.listTextures.addItem(texture.file_name)

        # Update effects list
        self.listTextures.clearSelection()
        self.listTextures.setCurrentRow(new_index)

        self.status(f"Imported {new_texture_count} texture(s), replaced {replaced_entries} existing texture(s).", StatusColor.INFO)

    def delete_textures(self):
        if self.get_editor_mode() != PgpEditorMode.TEXTURE:
            return
        if len(self.listTextures.selectedItems()) == 0:
            self.status("No texture(s) selected!", StatusColor.ERROR)
            return

        # Get selected list indexes
        delete_indexes = [i.row() for i in self.listTextures.selectionModel().selectedIndexes()]

        # The selected indexes are shuffled, so we remove particles starting from the end of the list
        delete_indexes.sort(reverse=True)

        # Go through indexes and delete list item and the actual particle
        for delete_index in delete_indexes:
            key = self.listTextures.takeItem(delete_index).text()
            self.particle_data.textures.pop(key)

        self.status(f"Deleted {len(delete_indexes)} texture(s).", StatusColor.INFO)

    def export_textures(self):
        if self.get_editor_mode() != PgpEditorMode.TEXTURE:
            return
        if len(self.listTextures.selectedItems()) == 0:
            self.status("No texture(s) selected!", StatusColor.ERROR)
            return

        export_folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Export textures to...")
        if len(export_folder) == 0:
            return

        texture_names = [t.text() for t in self.listTextures.selectedItems()]

        for texture_name in texture_names:
            fp_out_texture = os.path.join(export_folder, f"{texture_name}.bti")
            pyaurum.write_file(fp_out_texture, self.particle_data.textures[texture_name].bti_data)

        self.status(f"Exported {len(texture_names)} texture(s) to \"{export_folder}\".", StatusColor.INFO)


def dump_particle_data(in_folder: str, out_folder: str):
    """
    Loads all data from Particles.jpc, ParticleNames.bcsv and AutoEffectList.bcsv and dumps the retrieved data to
    readable and editable JSON files. The particle textures will be stored as BTI images in a separate folder.
    The following files have to be supplied:
    - 'in_folder'/Particles.jpc
    - 'in_folder'/ParticleNames.bcsv
    - 'in_folder'/AutoEffectList.bcsv

    The output files and structure look like this:
    - 'out_folder'/Particles.json
    - 'out_folder'/Effects.json
    - 'out_folder'/Particles/<particle name>.json
    - 'out_folder'/Textures/<texture name>.bti

    Particles.json contains lists of particles and textures that belong to the particles container. If you want
    to add new particles and textures, make sure to add their names to the respective lists. Effects.json is a
    simplified version of AutoEffectList containing only the non-default values for every effect.
    """
    # Setup input file paths
    fp_particles = os.path.join(in_folder, "Particles.jpc")
    fp_particle_names = os.path.join(in_folder, "ParticleNames.bcsv")
    fp_effects = os.path.join(in_folder, "AutoEffectList.bcsv")

    # Setup output file paths
    fp_out_particles_json = os.path.join(out_folder, "Particles.json")
    fp_out_particles = os.path.join(out_folder, "Particles")
    fp_out_textures = os.path.join(out_folder, "Textures")
    fp_out_effects_json = os.path.join(out_folder, "Effects.json")

    # Unpack data from JPC and BCSV files
    pd = mrformats.ParticleData()
    pd.unpack_bin(fp_particles, fp_particle_names, fp_effects)

    # Dump data to JSON and BTI files
    pd.pack_json(fp_out_particles_json, fp_out_particles, fp_out_textures, fp_out_effects_json)


def pack_particle_data(in_folder: str, out_folder: str):
    """
    Packs particle data using the information located in 'in_folder'. Please refer to above function's documentation
    if you want to see what each file's usage is.
    The following files and folders have to be supplied:
    - 'in_folder'/Particles.json
    - 'in_folder'/Effects.json
    - 'in_folder'/Particles/<particle name>.json
    - 'in_folder'/Textures/<texture name>.bti

    The output files look like this:
    - 'out_folder'/Particles.jpc
    - 'out_folder'/ParticleNames.bcsv
    - 'out_folder'/AutoEffectList.bcsv
    """
    # Setup input file paths
    fp_particles_json = os.path.join(in_folder, "Particles.json")
    fp_particles = os.path.join(in_folder, "Particles")
    fp_textures = os.path.join(in_folder, "Textures")
    fp_effects_json = os.path.join(in_folder, "Effects.json")

    # Setup output file paths
    fp_out_particles = os.path.join(out_folder, "Particles.jpc")
    fp_out_particle_names = os.path.join(out_folder, "ParticleNames.bcsv")
    fp_out_effects = os.path.join(out_folder, "AutoEffectList.bcsv")

    # Load data from JSON and BTI files
    pd = mrformats.ParticleData()
    pd.unpack_json(fp_particles_json, fp_particles, fp_textures, fp_effects_json)

    # Pack data to JPC and BCSV files
    pd.pack_bin(fp_out_particles, fp_out_particle_names, fp_out_effects)


if __name__ == "__main__":
    # Batch mode
    if len(sys.argv) > 1:
        parser = argparse.ArgumentParser(description="pygapa")
        parser.add_argument("mode", type=str)
        parser.add_argument("in_dir", type=str)
        parser.add_argument("out_dir", type=str)
        args = parser.parse_args()

        if args.mode == "dump":
            dump_particle_data(args.in_dir, args.out_dir)
        elif args.mode == "pack":
            pack_particle_data(args.in_dir, args.out_dir)
    # Editor mode
    else:
        main_window = PgpEditor()
        sys.exit(PROGRAM.exec_())
