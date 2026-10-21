import bpy
from bpy.props import EnumProperty, FloatVectorProperty

from ..bindings import dynamic_paint
from ..builders import common
from ..core import orchestrator
from ..engines import registry
from ..engines.fluid import roles as fluid_roles
from ..engines.fluid import scenarios as fluid_scenarios
from ..services import floaters
from ..services.water_query import FlatWater

ROLE_ITEMS = [("OBSTACLE", "Obstacle", "Static or animated collision object"),
              ("TERRAIN", "Terrain", "Bed or shore collision object"),
              ("SOURCE", "Source", "Liquid inflow"), ("SINK", "Sink", "Liquid outflow"),
              ("BLOCK", "Block", "Initial liquid volume"), ("FLOATER", "Floater", "Object floating on the water")]


def _active(context):
    return context.scene.flowfx.active_body()


class FLOWFX_OT_role_assign(bpy.types.Operator):
    bl_idname = "flowfx.role_assign"
    bl_label = "Assign Role"
    bl_description = "Give the selected objects a role in the active water body"
    bl_options = {"REGISTER", "UNDO"}

    role: EnumProperty(name="Role", items=ROLE_ITEMS, default="OBSTACLE")
    velocity: FloatVectorProperty(name="Velocity (m/s)", size=3, default=(0.0, 0.0, 0.0))

    @classmethod
    def poll(cls, context):
        return _active(context) is not None and bool(context.selected_objects)

    def execute(self, context):
        item = _active(context)
        n = 0
        for obj in context.selected_objects:
            if obj.type != "MESH":
                continue
            if item.engine == "fluid":
                vel = tuple(self.velocity) if any(self.velocity) else None
                fluid_roles.assign_role(obj, self.role, item.uid, velocity=vel)
            elif self.role == "FLOATER":
                common.tag(obj, item.uid, "FLOATER")
            elif self.role == "OBSTACLE":
                dynamic_paint.add_brush(obj)
                common.tag(obj, item.uid, "OBSTACLE")
            else:
                self.report({"WARNING"}, f"Role {self.role} needs a Fluid body")
                continue
            n += 1
        self.report({"INFO"}, f"Assigned {self.role} to {n} object(s)")
        return {"FINISHED"} if n else {"CANCELLED"}


class FLOWFX_OT_role_clear(bpy.types.Operator):
    bl_idname = "flowfx.role_clear"
    bl_label = "Clear Role"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return bool(context.selected_objects)

    def execute(self, context):
        for obj in context.selected_objects:
            fluid_roles.clear_role(obj)
        return {"FINISHED"}


class FLOWFX_OT_wavemaker_add(bpy.types.Operator):
    bl_idname = "flowfx.wavemaker_add"
    bl_label = "Add Wavemaker"
    bl_description = "Add a piston wavemaker (Biesel transfer function) to the active fluid body"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        item = _active(context)
        return item is not None and item.engine == "fluid"

    def execute(self, context):
        fx = context.scene.flowfx
        item = fx.active_body()
        ctx = orchestrator.build_context(context, item)
        dom = common.objects_of(item.uid, "DOMAIN")[0]
        width = dom.dimensions.y or 8.0
        coll = common.body_collection(context.scene, item.uid, item.title)
        paddle, stroke = fluid_scenarios.add_wavemaker(ctx, coll, width, fx.wave_height_m, fx.wave_period_s,
                                                       fx.wave_depth_m, context.scene.render.fps)
        self.report({"INFO"}, f"Piston stroke {stroke:.2f} m")
        return {"FINISHED"}


class FLOWFX_OT_floater_bake(bpy.types.Operator):
    bl_idname = "flowfx.floater_bake"
    bl_label = "Bake Floater"
    bl_description = "Simulate the active object floating on the active body and bake location/rotation keyframes"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return _active(context) is not None and context.active_object is not None

    def execute(self, context):
        fx = context.scene.flowfx
        item, obj, scene = fx.active_body(), context.active_object, context.scene
        dims = tuple(max(d, 0.05) for d in obj.dimensions)
        spec = floaters.FloaterSpec(mass=fx.float_mass_kg, size=dims, nsamples=(6, 6, 10), linear_damping=500.0,
                                    angular_damping=200.0)
        try:
            query = registry.get(item.engine).query(orchestrator.build_context(context, item))
        except NotImplementedError:
            query = FlatWater(0.0)
        fps = scene.render.fps
        duration = (scene.frame_end - scene.frame_start) / fps
        ts, ps, qs = floaters.simulate(spec, query, duration, dt=1 / 240, position=tuple(obj.location),
                                       sample_dt=1 / fps)
        floaters.bake_to_fcurves(obj, ts, ps, qs, fps, scene.frame_start)
        common.tag(obj, item.uid, "FLOATER")
        self.report({"INFO"}, f"Baked {len(ts)} frames")
        return {"FINISHED"}


classes = (FLOWFX_OT_role_assign, FLOWFX_OT_role_clear, FLOWFX_OT_wavemaker_add, FLOWFX_OT_floater_bake)
