# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2024 Yorik van Havre <yorik@uncreated.net>              *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU General Public License (GPL)            *
# *   as published by the Free Software Foundation; either version 3 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU General Public License for more details.                          *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with this program; if not, write to the Free Software   *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************

import FreeCAD
import Draft
import ifcopenshell

from importers import exportIFC
from importers import exportIFCHelper
from importers import importIFCHelper

from nativeifc import ifc_tools


def get_export_preferences(ifcfile):
    """returns a preferences dict for exportIFC"""

    prefs = exportIFC.getPreferences()
    prefs["SCHEMA"] = ifcfile.wrapped_data.schema_name()
    s = ifcopenshell.util.unit.calculate_unit_scale(ifcfile)
    # the above lines yields meter -> file unit scale factor. We need mm
    prefs["SCALE_FACTOR"] = 0.001 / s
    context = ifcfile[
        ifc_tools.get_body_context_ids(ifcfile)[0]
    ]  # we take the first one (first found subcontext)
    return prefs, context


def create_product(obj, parent, ifcfile, ifcclass=None):
    """Creates an IFC product out of a FreeCAD object"""

    name = obj.Label
    description = getattr(obj, "Description", None)
    if not ifcclass:
        ifcclass = ifc_tools.get_ifctype(obj)
    representation, placement = create_representation(obj, ifcfile)
    product = ifc_tools.api_run("root.create_entity", ifcfile, ifc_class=ifcclass, name=name)
    ifc_tools.set_attribute(ifcfile, product, "Description", description)
    ifc_tools.set_attribute(ifcfile, product, "ObjectPlacement", placement)
    # TODO below cannot be used at the moment because the ArchIFC exporter returns an
    # IfcProductDefinitionShape already and not an IfcShapeRepresentation
    # ifc_tools.api_run("geometry.assign_representation", ifcfile, product=product, representation=representation)
    ifc_tools.set_attribute(ifcfile, product, "Representation", representation)
    # TODO treat subtractions/additions
    return product


def create_representation(obj, ifcfile):
    """Creates a geometry representation for the given object"""

    # TEMPORARY use the Arch exporter
    # TODO this is temporary. We should rely on ifcopenshell for this with:
    # https://blenderbim.org/docs-python/autoapi/ifcopenshell/api/root/create_entity/index.html
    # a new FreeCAD 'engine' should be added to:
    # https://blenderbim.org/docs-python/autoapi/ifcopenshell/api/geometry/index.html
    # that should contain all typical use cases one could have to convert FreeCAD geometry
    # to IFC.

    # setup exporter - TODO do that in the module init
    exportIFC.clones = {}
    exportIFC.profiledefs = {}
    exportIFC.surfstyles = {}
    exportIFC.shapedefs = {}
    exportIFC.ifcopenshell = ifcopenshell
    exportIFC.ifcbin = exportIFCHelper.recycler(ifcfile, template=False)
    prefs, context = get_export_preferences(ifcfile)
    representation, placement, shapetype = exportIFC.getRepresentation(
        ifcfile, context, obj, preferences=prefs
    )
    return representation, placement


def is_annotation(obj):
    """Determines if the given FreeCAD object should be saved as an IfcAnnotation"""

    if getattr(obj, "IfcClass", None) == "IfcAnnotation":
        return True
    if getattr(obj, "IfcType", None) == "Annotation":
        return True
    if obj.isDerivedFrom("Part::Part2DObject"):
        return True
    elif obj.isDerivedFrom("App::Annotation"):
        return True
    elif Draft.getType(obj) in ["DraftText",
                                "Text",
                                "Dimension",
                                "LinearDimension",
                                "AngularDimension"]:
        return True
    elif obj.isDerivedFrom("Part::Feature"):
        if obj.Shape and (not obj.Shape.Solids) and obj.Shape.Edges:
            if not obj.Shape.Faces:
                return True
            elif (obj.Shape.BoundBox.XLength < 0.0001) \
                or (obj.Shape.BoundBox.YLength < 0.0001) \
                or (obj.Shape.BoundBox.ZLength < 0.0001):
                return True
    return False


def get_text(annotation):
    """Determines if an IfcAnnotation contains an IfcTextLiteral.
    Returns the IfcTextLiteral or None"""

    for rep in annotation.Representation.Representations:
        for item in rep.Items:
            if item.is_a("IfcTextLiteral"):
                return item
    return None


def create_annotation(obj, ifcfile):
    """Adds an IfcAnnotation from the given object to the given IFC file"""

    exportIFC.clones = {}
    exportIFC.profiledefs = {}
    exportIFC.surfstyles = {}
    exportIFC.shapedefs = {}
    exportIFC.curvestyles = {}
    exportIFC.ifcopenshell = ifcopenshell
    exportIFC.ifcbin = exportIFCHelper.recycler(ifcfile, template=False)
    prefs, context = get_export_preferences(ifcfile)
    history = get_history(ifcfile)
    # TODO The following prints each edge as a separate IfcGeometricCurveSet
    # It should be refined to create polylines instead
    anno = exportIFC.create_annotation(obj, ifcfile, context, history, prefs)
    return anno


def get_history(ifcfile):
    """Returns the owner history or None"""

    history = ifcfile.by_type("IfcOwnerHistory")
    if history:
        history = history[0]
    else:
        # IFC4 allows to not write any history
        history = None
    return history


def get_placement(ifcelement, ifcfile):
    """Returns a FreeCAD placement from an IFC placement"""

    s = 0.001 / ifcopenshell.util.unit.calculate_unit_scale(ifcfile)
    return importIFCHelper.getPlacement(ifcelement, scaling=s)
