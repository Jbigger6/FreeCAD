# SPDX-License-Identifier: LGPL-2.1-or-later

# ***************************************************************************
# *                                                                         *
# *   This file is part of FreeCAD.                                         *
# *                                                                         *
# *   FreeCAD is free software: you can redistribute it and/or modify it    *
# *   under the terms of the GNU Lesser General Public License as           *
# *   published by the Free Software Foundation, either version 2.1 of the  *
# *   License, or (at your option) any later version.                       *
# *                                                                         *
# *   FreeCAD is distributed in the hope that it will be useful, but        *
# *   WITHOUT ANY WARRANTY; without even the implied warranty of            *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU      *
# *   Lesser General Public License for more details.                       *
# *                                                                         *
# *   You should have received a copy of the GNU Lesser General Public      *
# *   License along with FreeCAD. If not, see                               *
# *   <https://www.gnu.org/licenses/>.                                      *
# *                                                                         *
# ***************************************************************************

"""The BIM Align command."""

import FreeCAD
import FreeCADGui

QT_TRANSLATE_NOOP = FreeCAD.Qt.QT_TRANSLATE_NOOP
translate = FreeCAD.Qt.translate


class BIM_Align:
    """Aligns an object by moving it until a chosen edge is coincident with a reference edge.

    Workflow:
      1. Activate the tool.
      2. Click the reference edge (the edge to align TO).
      3. Click the edge on the object you want to move.
      The target object is translated so the midpoint of its selected edge
      meets the midpoint of the reference edge.
    """

    def GetResources(self):
        return {
            "Pixmap": "BIM_Align",
            "Accel": "A, L",
            "MenuText": QT_TRANSLATE_NOOP("BIM_Align", "Align"),
            "ToolTip": QT_TRANSLATE_NOOP(
                "BIM_Align",
                "Aligns an object to a reference edge.\n"
                "Click the reference edge, then click the edge of the object to align.\n"
                "Press Escape to cancel.",
            ),
        }

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        self._ref_edge = None
        self._ref_obj = None
        self._call = None
        self._view = FreeCADGui.ActiveDocument.ActiveView
        self._call = self._view.addEventCallback("SoEvent", self._on_event)
        FreeCAD.Console.PrintMessage(
            translate("BIM", "Align: click the reference edge (the edge to align to)") + "\n"
        )

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    def _on_event(self, event):
        if self._view is None:
            return
        if event.get("Type") == "SoKeyboardEvent":
            if event.get("Key") == "ESCAPE":
                FreeCAD.Console.PrintMessage(translate("BIM", "Align: cancelled") + "\n")
                self._finish()
            return

        if event.get("Type") != "SoMouseButtonEvent":
            return
        if event.get("State") != "DOWN" or event.get("Button") != "BUTTON1":
            return

        pos = event["Position"]
        snapped = self._view.getObjectInfo((pos[0], pos[1]))

        if not snapped or not snapped.get("Component", "").startswith("Edge"):
            FreeCAD.Console.PrintMessage(
                translate("BIM", "Align: please click directly on an edge") + "\n"
            )
            return

        obj = FreeCAD.ActiveDocument.getObject(snapped["Object"])
        if obj is None or not hasattr(obj, "Shape"):
            return
        if not obj.Shape.Solids:
            FreeCAD.Console.PrintMessage(
                translate("BIM", "Align: please click an edge on a solid object (not a level, axis, or annotation)") + "\n"
            )
            return

        edge_idx = int(snapped["Component"][4:]) - 1
        edge = obj.Shape.Edges[edge_idx]

        if self._ref_edge is None:
            self._ref_edge = edge
            self._ref_obj = obj
            FreeCAD.Console.PrintMessage(
                translate("BIM", "Align: now click the edge of the object to align") + "\n"
            )
        else:
            if obj is self._ref_obj:
                FreeCAD.Console.PrintMessage(
                    translate("BIM", "Align: please click an edge on a different object") + "\n"
                )
                return
            FreeCAD.ActiveDocument.openTransaction("BIM Align")
            try:
                self._apply_alignment(obj, edge)
                FreeCAD.ActiveDocument.commitTransaction()
            except Exception as exc:
                FreeCAD.ActiveDocument.abortTransaction()
                FreeCAD.Console.PrintError(translate("BIM", "Align: failed") + " - " + str(exc) + "\n")
            self._finish()

    # ------------------------------------------------------------------
    # Alignment math
    # ------------------------------------------------------------------

    def _apply_alignment(self, target_obj, target_edge):
        """Translate target_obj so target_edge's midpoint meets the reference edge's midpoint,
        constrained to the axis perpendicular to the reference edge.

        A vertical edge (runs in Y) → move only in X.
        A horizontal edge (runs in X) → move only in Y.
        Generalised: the component of the translation along the edge direction is zeroed out,
        leaving only the perpendicular component(s).
        """
        ref_mid = _edge_midpoint(self._ref_edge)
        tgt_mid = _edge_midpoint(target_edge)
        world_delta = ref_mid - tgt_mid

        # Remove the component of the translation that runs along the reference edge.
        edge_dir = _edge_direction(self._ref_edge)
        if edge_dir is not None:
            along = world_delta.dot(edge_dir)
            world_delta = world_delta - edge_dir * along

        # Rotate world-space delta into the local frame of any parent container.
        parent_rot = _parent_rotation(target_obj)
        local_delta = parent_rot.inverted().multVec(world_delta)

        target_obj.Placement = FreeCAD.Placement(
            target_obj.Placement.Base + local_delta,
            target_obj.Placement.Rotation,
        )
        FreeCAD.ActiveDocument.recompute()
        FreeCAD.Console.PrintMessage(translate("BIM", "Align: done") + "\n")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _finish(self):
        if self._call:
            try:
                self._view.removeEventCallback("SoEvent", self._call)
            except Exception:
                pass
        self._call = None
        self._ref_edge = None
        self._ref_obj = None
        self._view = None


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _edge_midpoint(edge):
    """Return the midpoint of a linear or curved edge in world space."""
    if len(edge.Vertexes) >= 2:
        return (edge.Vertexes[0].Point + edge.Vertexes[-1].Point) * 0.5
    return edge.Vertexes[0].Point


def _edge_direction(edge):
    """Return the normalised direction vector of an edge, or None if degenerate."""
    if len(edge.Vertexes) < 2:
        return None
    vec = edge.Vertexes[-1].Point - edge.Vertexes[0].Point
    length = vec.Length
    if length < 1e-10:
        return None
    return vec / length


def _parent_rotation(obj):
    """Return the global rotation of the closest Group-type parent, or identity."""
    for parent in obj.InList:
        if hasattr(parent, "Group") and obj in parent.Group:
            if hasattr(parent, "getGlobalPlacement"):
                return parent.getGlobalPlacement().Rotation
            if hasattr(parent, "Placement"):
                return parent.Placement.Rotation
    return FreeCAD.Rotation()


FreeCADGui.addCommand("BIM_Align", BIM_Align())
