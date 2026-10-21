
import bpy
from bpy.props import EnumProperty

from ..bindings import fluid as fluid_binding
from ..builders import common
from ..core import jobs, orchestrator
from ..engines import registry
from ..engines.spectral import bake as spectral_bake
from ..services import cache as cache_service

CURRENT: dict = {"job": None}


def _active(context):
    return context.scene.flowfx.active_body()


def _make_generator(context, item):
    """Return (generator yielding (done, total), finalize callable) for the active body, or None for UI-driven."""
    ctx = orchestrator.build_context(context, item)
    engine = registry.get(item.engine)
    if item.engine == "spectral":
        obj = common.objects_of(item.uid, "SURFACE")[0]
        out = str(ctx.cache_dir / "spectral")
        gen = ((d, t) for d, t, _p in spectral_bake.bake_displacement_iter(obj, context.scene, out))
        return gen, (lambda: None)
    if item.engine == "heightfield":
        return engine.bake_iter(ctx), (lambda: engine.finish_bake(ctx))
    return None, None


class FLOWFX_OT_bake(bpy.types.Operator):
    bl_idname = "flowfx.bake"
    bl_label = "Bake"
    bl_description = "Bake the active body. Spectral and Heightfield run as a cancellable modal job; Fluid starts Blender's bake"
    bl_options = {"REGISTER"}

    stage: EnumProperty(name="Stage", items=[("all", "All", ""), ("data", "Data", ""), ("mesh", "Mesh", ""),
                                             ("particles", "Particles", "")], default="all")
    _timer = None
    _gen = None
    _finalize = None
    _job = None

    @classmethod
    def poll(cls, context):
        return _active(context) is not None

    def _begin(self, context):
        item = _active(context)
        if item.engine == "fluid":
            dom = common.objects_of(item.uid, "DOMAIN")[0]
            fluid_binding.bake(dom, self.stage, context.scene)
            return "fluid"
        if item.engine == "interaction":
            self.report({"INFO"}, "Dynamic Paint Waves is cached by Blender; play the timeline to simulate")
            return "none"
        self._gen, self._finalize = _make_generator(context, item)
        self._job = jobs.Job(f"bake {item.title}", steps=1)
        CURRENT["job"] = self._job
        return "job"

    def execute(self, context):
        """Synchronous bake (used by scripts and tests)."""
        kind = self._begin(context)
        if kind != "job":
            return {"FINISHED"}
        self._job.start()
        for done, total in self._gen:
            self._job.steps, self._job.done = total, done
        self._finalize()
        self._job.finish()
        return {"FINISHED"}

    def invoke(self, context, event):
        kind = self._begin(context)
        if kind != "job":
            return {"FINISHED"}
        self._job.start()
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.01, window=context.window)
        wm.modal_handler_add(self)
        wm.progress_begin(0, 100)
        return {"RUNNING_MODAL"}

    def _end(self, context):
        wm = context.window_manager
        if self._timer is not None:
            wm.event_timer_remove(self._timer)
        wm.progress_end()
        CURRENT["job"] = None

    def modal(self, context, event):
        if event.type == "ESC" or self._job.cancel_requested:
            self._job.cancel()
            self._end(context)
            self._finalize() if self._job.done else None
            self._job.finish()
            self.report({"WARNING"}, "Bake cancelled")
            return {"CANCELLED"}
        if event.type == "TIMER":
            try:
                done, total = next(self._gen)
            except StopIteration:
                self._finalize()
                self._job.finish()
                self._end(context)
                self.report({"INFO"}, "Bake finished")
                return {"FINISHED"}
            self._job.steps, self._job.done = total, done
            context.window_manager.progress_update(int(100 * done / max(total, 1)))
        return {"RUNNING_MODAL"}


class FLOWFX_OT_bake_cancel(bpy.types.Operator):
    bl_idname = "flowfx.bake_cancel"
    bl_label = "Cancel Bake"

    @classmethod
    def poll(cls, context):
        return CURRENT["job"] is not None

    def execute(self, context):
        CURRENT["job"].cancel()
        return {"FINISHED"}


class FLOWFX_OT_cache_free(bpy.types.Operator):
    bl_idname = "flowfx.cache_free"
    bl_label = "Free Cache"
    bl_description = "Delete the active body's baked files"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return _active(context) is not None

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        item = _active(context)
        ctx = orchestrator.build_context(context, item)
        removed = cache_service.free(ctx.cache_dir)
        if item.engine == "fluid":
            try:
                fluid_binding.free(common.objects_of(item.uid, "DOMAIN")[0], "all", context.scene)
            except Exception:  # noqa: BLE001 - UI-only operator may be unavailable
                pass
        self.report({"INFO"}, f"Removed {removed} cache file(s)")
        return {"FINISHED"}


classes = (FLOWFX_OT_bake, FLOWFX_OT_bake_cancel, FLOWFX_OT_cache_free)
