#Author-Autodesk
#Description-Demonstrates the creation of a custom feature.

from dis import dis
from pickletools import ArgumentDescriptor
import re
from tkinter import E
from tkinter.messagebox import NO
from venv import create
import adsk.core, adsk.fusion, traceback
import logging
import os
from .decorators import eventHandler, HandlerCollection, timelineMarkers
appPath = os.path.dirname(os.path.abspath(__file__))

logger = logging.getLogger('customCove')

if len(logger.handlers):
    del logger.handlers[:]

logger.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s; %(name)s; %(levelname)s; %(lineno)d; %(funcName)s ; %(message)s')
logHandler = logging.FileHandler(os.path.join(appPath, 'customFeatureExample.log'), mode='w')
logHandler.setFormatter(formatter)
logHandler.setLevel(logging.DEBUG)
logger.addHandler(logHandler)
logger.setLevel(logging.DEBUG)

_app: adsk.core.Application = None
_ui: adsk.core.UserInterface = None
_des: adsk.fusion.Design = None
_root = None

_edge_token = None

_customFeatureDef: adsk.fusion.CustomFeature = None

_edgeSelectInput: adsk.core.SelectionCommandInput = None
_radiusInput: adsk.core.ValueCommandInput = None

_alreadyCreatedCustomFeature: adsk.fusion.CustomFeature = None
_restoreTimelineObject: adsk.fusion.TimelineObject = None
# _alreadyCreated: bool = False
_isRolledForEdit = False
_compute_handler = None
_start_tl_object = None
_active_custom_feature = None

class NotInRolledBackState(Exception):
    pass

def run(context):
    try:
        global _app, _ui, _des, _root
        global _compute_handler
        _app = adsk.core.Application.get()
        _ui  = _app.userInterface
        _des = _app.activeProduct
        _root = _des.rootComponent
        
        handlerGroup = 'run'
        logger.debug("Running")
        # Create the command definition for the creation command.
        createCmdDef = _ui.commandDefinitions.addButtonDefinition('adskCustomCoveCreate', 
                                                                    'Custom Cove', 
                                                                    'Adds a pocket at a point.', 
                                                                    'Resources/CustomCove')    

        # Add the create button after the Emboss command in the CREATE panel of the SOLID tab.
        solidWS = _ui.workspaces.itemById('FusionSolidEnvironment')
        panel = solidWS.toolbarPanels.itemById('SolidCreatePanel')
        btncontrol = panel.controls.addCommand(createCmdDef, 'EmbossCmd', False).isPromoted = True
        # btncontrol.isPromoted = True      

        # Create the command definition for the edit command.
        editCmdDef = _ui.commandDefinitions.addButtonDefinition('adskCustomCoveEdit', 
                                                                'Edit Custom Cove', 
                                                                'Edit custom pocket.', '')        

        # Connect to the command created event for the create command.
        HandlerCollection.remove(groupId =  handlerGroup)
        on_create_handler(event = createCmdDef.commandCreated, groupId =  handlerGroup)

        # Connect to the command created event for the edit command.
        on_create_edit_handler(event = editCmdDef.commandCreated, groupId =  handlerGroup)

        # Create the custom feature definition.
        global _customFeatureDef
        _customFeatureDef = adsk.fusion.CustomFeatureDefinition.create('adskCustomCove', 
                                                                        'Custom Cove', 
                                                                        'Resources/CustomCove')
        _customFeatureDef.editCommandId = 'adskCustomCoveEdit'

        # Connect to the compute event for the custom feature.
        _compute_handler = on_compute_custom_feature(event = _customFeatureDef.customFeatureCompute, groupId =  handlerGroup)
    except:
        logger.exception('Exception')
        showMessage('Run Failed:\n{}'.format(traceback.format_exc()))


def stop(context):
    logger.debug('Stopping')
    if len(logger.handlers):
        del logger.handlers[:]
    try:
        # Remove all UI elements.
        logger.debug('Stopping')
        solidWS = _ui.workspaces.itemById('FusionSolidEnvironment')
        panel = solidWS.toolbarPanels.itemById('SolidCreatePanel')
        cntrl = panel.controls.itemById('adskCustomCoveCreate')
        if cntrl:
            cntrl.deleteMe()
            
        cmdDef = _ui.commandDefinitions.itemById('adskCustomCoveCreate')
        if cmdDef:
            cmdDef.deleteMe()

        cmdDef = _ui.commandDefinitions.itemById('adskCustomCoveEdit')
        if cmdDef:
            cmdDef.deleteMe()

        HandlerCollection.remove()
    except:
        logger.exception('Exception')
        showMessage('Stop Failed:\n{}'.format(traceback.format_exc()))


# Define the command inputs needed to get the input from the user for the
# creation of the feauture and connect to the command related events.
@eventHandler(handler_cls = adsk.core.CommandCreatedEventHandler)
@timelineMarkers
def on_create_handler(eventArgs: adsk.core.CommandCreatedEventArgs):
    try:
        global _edgeSelectInput, _radiusInput
        global _des, _root, _start_tl_object

        root: adsk.fusion.Component = _root
        
        logger.debug('Creating Cove Command')
        handlerGroup = 'on_create_handler'
        cmd = eventArgs.command
        inputs = cmd.commandInputs
        des: adsk.fusion.Design = _des

        # Create the selection input to select the body(s).
        _edgeSelectInput = inputs.addSelectionInput('selectEdge', 
                                                        'Edges', 
                                                        'Select edge to define cove location.')
        _edgeSelectInput.addSelectionFilter('Edges')
        _edgeSelectInput.tooltip = 'Select edge to define the cove.'
        _edgeSelectInput.setSelectionLimits(1, 1)

        lengthUnits = des.unitsManager.defaultLengthUnits

        # Create the value input to get the fillet radius.
        radius = adsk.core.ValueInput.createByReal(0.5)
        inputs.addValueInput('radius', 'Corner Radius', lengthUnits, radius)

        # Connect to the needed command related events.
        HandlerCollection.remove(handlerGroup)

        on_preview_handler(event = cmd.executePreview, groupId = handlerGroup)

        on_execute_handler(event = cmd.execute, groupId = handlerGroup)

        on_preselect_handler(event = cmd.preSelect, groupId = handlerGroup)

        on_change_handler(event = cmd.inputChanged, groupId = handlerGroup)

        on_activate_handler(event = cmd.activate, groupId = handlerGroup)

        on_validate_inputs_handler(event = cmd.validateInputs, groupId = handlerGroup)
    except:
        logger.exception('Exception')
        showMessage(f'CommandCreated failed: {traceback.format_exc()}\n')

@eventHandler(handler_cls = adsk.core.CommandEventHandler)
def on_activate_handler(args: adsk.core.CommandEventArgs):
    logger.debug('on_activate_handler')

    global _des, _root
    global _customFeatureDef, _active_custom_feature
    global _start_tl_object
    cmd = args.command
    radiusCommandInput:adsk.core.ValueCommandInput = cmd.commandInputs.itemById('radius')
    radiusInput = adsk.core.ValueInput.createByString(radiusCommandInput.expression)
    des: adsk.fusion.Design = _des
    root: adsk.fusion.Component = _root
    tempEdge = root.bRepBodies.item(0).edges.item(0)

    marker_pos = des.timeline.markerPosition
    _start_tl_object = des.timeline.item(marker_pos-1)

    customFeatureInput = root.features.customFeatures.createInput(_customFeatureDef)

    lengthUnits = des.unitsManager.defaultLengthUnits
    customFeatureInput.addCustomParameter('radius', 'Radius', radiusInput, lengthUnits, True)
    customFeatureInput.addDependency('edge', tempEdge)

    _compute_handler.disableOnce()
    customFeature = root.features.customFeatures.add(customFeatureInput) 
    #^^^creates new customFeature object in timeline^^^

    # cmd.editingFeature = customFeature
    _active_custom_feature = customFeature

    _active_custom_feature.timelineObject.rollTo(False)

    # cmd.beginStep()
    pass

@eventHandler(handler_cls = adsk.core.InputChangedEventHandler)
def on_change_handler(eventArgs: adsk.core.InputChangedEventArgs):
    logger.debug('on_change_handler') 
    global _root, _des, _ui
    global _edge_token

    root:adsk.fusion.Component = _root
    des:adsk.fusion.Design = _des
    ui: adsk.core.UserInterface = _ui

    input:adsk.core.CommandInput = eventArgs.input
    inputs: adsk.core.CommandInputs = eventArgs.inputs
    # customFeature:adsk.fusion.CustomFeature = eventArgs.inputs.command.editingFeature
    customFeature: adsk.fusion.CustomFeature = _active_custom_feature

    if input.id == 'selectEdge':
        edge = input.selection(0).entity
        try:
            activeEdge = customFeature.dependencies.itemById('edge').entity
            _edge_token = edge.entityToken
        except Exception:
            activeEdge = None  #this is a workaround - itemById is supposed to return NULL if not found
        if not edge:  #Edge has been unselected
            if not activeEdge:
                return
            activeEdge.deleteMe()
            return

        #edge has been selected

        if not activeEdge:
            customFeature.timelineObject.rollTo(True)
            _compute_handler.disableOnce()
            customFeature.dependencies.add('edge', edge)
            _edge_token = edge.entityToken
            customFeature.timelineObject.rollTo(False)
            ui.activeSelections.add(edge)
            return

        _compute_handler.disableOnce()
        customFeature.dependencies.itemById('edge').entity = edge
        # _ = eventArgs.firingEvent.sender.doExecutePreview()
        return

    radiusValueInput = inputs.itemById('radius').expression
    radiusValue = adsk.core.ValueInput.createByString(radiusValueInput)

    # _compute_handler.disableOnce()
    customFeature.parameters.itemById('radius').expression = eventArgs.inputs.itemById('radius').expression

    eventArgs.firingEvent.sender.beginStep()

# Event handler for the validateInputs event.
@eventHandler(handler_cls = adsk.core.ValidateInputsEventHandler)
def on_validate_inputs_handler(eventArgs: adsk.core.ValidateInputsEventArgs):
    logger.debug('on_validate_inputs_handler')
    try:

        # return eventArgs.inputs.itemById('radius').isValidExpression
        # Verify the inputs have valid expressions.
        if not all( [eventArgs.inputs.itemById('radius').isValidExpression,
                    eventArgs.inputs.itemById('selectEdge').isValid] ):
            eventArgs.areInputsValid = False
            return
        eventArgs.areInputsValid = True
    except:
        logger.exception('Exception')
        showMessage(f'on_validate_inputs_handler: {traceback.format_exc()}\n')

        
# Event handler for the execute event of the create command.
@eventHandler(handler_cls = adsk.core.CommandEventHandler)
@timelineMarkers
def on_execute_handler(eventArgs: adsk.core.CommandEventArgs):
    global _compute_handler
    global _active_custom_feature
    global _des, _root, _start_tl_object
    global _edge_token

    logger.debug('on_execute_handler')
    # _compute_handler.disable()
    des: adsk.fusion.Design = _des
    root: adsk.fusion.Component = _root
    # _start_tl_object.rollTo(False)

    # custom_feature: adsk.fusion.CustomFeature = eventArgs.command.editingFeature
    custom_feature: adsk.fusion.CustomFeature = _active_custom_feature
    custom_feature.timelineObject.rollTo(True)

    try:
        # Create the body of the pocket.
        edge: adsk.fusion.BRepEdge = des.findEntityByToken(_edge_token)[0]
        radius = eventArgs.command.commandInputs.itemById('radius').value
        radiusValue = adsk.core.ValueInput.createByReal(radius)

        defLengthUnits = des.unitsManager.defaultLengthUnits

        covebody = CreateCove(edge, radius)

        comp = edge.body.parentComponent

        # Subtract the pocket from the parametric body.
        paramBody = edge.body
        comp = paramBody.parentComponent
        baseFeat = comp.features.baseFeatures.add()
        baseFeat.startEdit()
        comp.bRepBodies.add(covebody, baseFeat)
        baseFeat.finishEdit()

        # Create a combine feature to subtract the pocket body from the part.
        combineFeature = None
        toolBodies = adsk.core.ObjectCollection.create()
        toolBodies.add(baseFeat.bodies.item(0))
        combineInput = comp.features.combineFeatures.createInput(paramBody, toolBodies)
        combineInput.isKeepToolBodies = False
        combineInput.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
        combineFeature = comp.features.combineFeatures.add(combineInput)
        
        # Update the custom feature with start and end features.
        custom_feature.setStartAndEndFeatures(baseFeat, combineFeature)
        try:
            entity = custom_feature.dependencies.itemById('edge').entity
        except:
            entity = des. findEntityByToken(_edge_token)
            _compute_handler.disableOnce()
            custom_feature.dependencies.add('edge', edge)
        _ = custom_feature.timelineObject.rollTo(False)
        # _ = _start_tl_object.rollTo(False)
        pass
    except:
        logger.exception('Exception')
        eventArgs.executeFailed = True
        showMessage(f'Execute: {traceback.format_exc()}\n')


@eventHandler(handler_cls = adsk.core.CommandCreatedEventHandler)
def on_create_edit_handler(eventArgs: adsk.core.CommandCreatedEventArgs):
    global _compute_handler, _start_tl_object
    global _edgeSelectInput, _radiusInput
    global _des, _root

    
    logger.debug('on_create_edit_handler')
    try:
        handlerGroup = 'on_create_edit_handler'
        cmd = eventArgs.command
        inputs = cmd.commandInputs
        des: adsk.fusion.Design = _des
        defLengthUnits = des.unitsManager.defaultLengthUnits

        # Get the currently selected custom feature.
        currentCustomFeature: adsk.fusion.CustomFeature = _ui.activeSelections.item(0).entity
        if currentCustomFeature is None:
            return

        _start_tl_object = des.timeline.item(des.timeline.markerPosition)

        customFeatureTimelineObject = currentCustomFeature.timelineObject
        customFeatureTimelineObject.rollTo(rollBefore = True)

        # Create the selection input to select the sketch point.
        _edgeSelectInput = inputs.addSelectionInput('selectPoint', 
                                                        'edge', 
                                                        'Select point to define pocket position.')
        _edgeSelectInput.addSelectionFilter('SketchPoints')
        _edgeSelectInput.tooltip = 'Select point to define the center of the pocket.'
        _edgeSelectInput.setSelectionLimits(1, 1)

        # Get the collection of custom parameters for this custom feature.
        params = currentCustomFeature.parameters

        # Create the value input to get the fillet radius.
        radius = adsk.core.ValueInput.createByString(params.itemById('radius').expression)
        _radiusInput = inputs.addValueInput('radius', 'Corner Radius', defLengthUnits, radius)
                                            
        # Connect to the needed command related events.
        HandlerCollection.remove('on_execute_edit_handlerGroup')

        # cmd.editingFeature = currentCustomFeature

        on_preview_handler(event = cmd.executePreview, groupId =  handlerGroup)

        on_execute_edit_handler(event = cmd.execute, groupId =  handlerGroup)

        on_preselect_handler(event = cmd.preSelect, groupId =  handlerGroup)

        on_activate_edit_handler(event = cmd.activate, groupId =  handlerGroup)

        on_validate_inputs_handler(event = cmd.validateInputs, groupId =  handlerGroup)
    except:
        logger.exception('Exception')
        showMessage(f'CommandCreated failed: {traceback.format_exc()}\n')


# Event handler for the activate event.
@eventHandler(handler_cls = adsk.core.CommandEventHandler)
@timelineMarkers
def on_activate_edit_handler(args: adsk.core.CommandEventArgs):
    global _restoreTimelineObject, _isRolledForEdit
    global _des, _root

    
    logger.debug('on_activate_edit_handler')
    des: adsk.fusion.Design = _des
    try:

        currentCustomFeature: adsk.fusion.CustomFeature = _active_custom_feature
        # currentCustomFeature = args.command.editingFeature

        # Save the current position of the timeline.
        # timeline = des.timeline
        # currentPosition = timeline.markerPosition
        # _restoreTimelineObject = timeline.item(currentPosition - 1)

        _isRolledForEdit = True

        # Roll the timeline to just before the custom feature being edited.
        currentCustomFeature.timelineObject.rollTo(rollBefore = True)

        # Define a transaction marker so the the roll is not aborted with each change.

        # args the edge and add it to the selection input.
        edge = currentCustomFeature.dependencies.itemById('edge').entity
        _edgeSelectInput.addSelection(edge)
        args.command.beginStep()
    except:
        logger.exception('Exception')
        showMessage(f'Execute: {traceback.format_exc()}\n')


# Event handler for the execute event of the edit command.
@eventHandler(handler_cls = adsk.core.CommandEventHandler)
@timelineMarkers
def on_execute_edit_handler(args: adsk.core.CommandEventArgs):
    global _isRolledForEdit, _start_tl_object
    global _des, _root

    
    logger.debug('on_execute_edit_handler')

    des: adsk.fusion.Design = _des

    # customFeature: adsk.fusion.CustomFeature = args.command.editingFeature
    customFeature: adsk.fusion.CustomFeature = _active_custom_feature

    

    # timelineObject = customFeature.timelineObject

    # Roll the timeline to its previous position.
    # if not _isRolledForEdit:
    #     raise NotInRolledBackState

    try:

        edge = _edgeSelectInput.selection(0).entity

        # Update the parameters.
        params = customFeature.parameters

        radiusParam = params.itemById('radius')
        radiusParam.expression = args.command.commandInputs.itemById('radius').expression

        # Update the feature.
        UpdateCove(customFeature)

        # Update the point dependency.
        dependency = customFeature.dependencies.itemById('edge')
        dependency.entity = edge

        _start_tl_object.rollTo(False)

        showMessage('Finished ExecuteHandler')
    except:
        logger.exception('Exception')
        showMessage(f'Execute: {traceback.format_exc()}\n')

# Event handler for the executePreview event.
@eventHandler(handler_cls = adsk.core.CommandEventHandler)
@timelineMarkers
def on_preview_handler(eventArgs: adsk.core.CommandEventArgs):
    global _root, _des
    global _customFeatureDef
    global _start_tl_object
    global _edge_token

    des: adsk.fusion.Design = _des
    root: adsk.fusion.Component = _root
    # custom_feature = eventArgs.command.editingFeature
    custom_feature: adsk.fusion.CustomFeature = _active_custom_feature

    logger.debug('on_preview_handler')
    try:

        custom_feature.timelineObject.rollTo(True)
        # Get the settings from the inputs.

        # edge: adsk.fusion.BrepEdge = eventArgs.command.commandInputs.itemById('selectEdge').selection(0).entity
        edge: adsk.fusion.BRepEdge = des.findEntityByToken(_edge_token)[0]
        radius = eventArgs.command.commandInputs.itemById('radius').value
        radiusValue = adsk.core.ValueInput.createByReal(radius)

        # Create the fillet feature.
        covebody = CreateCove(edge, radius)

        # Create a base feature and add the body.
        paramBody = edge.body
        comp = paramBody.parentComponent

        baseFeat = comp.features.baseFeatures.add()
        baseFeat.startEdit()
        comp.bRepBodies.add(covebody, baseFeat)
        baseFeat.finishEdit()

        # Create a combine feature to subtract the pocket body from the part.
        toolBodies = adsk.core.ObjectCollection.create()
        toolBodies.add(baseFeat.bodies.item(0))
        combineInput = comp.features.combineFeatures.createInput(paramBody, toolBodies)
        combineInput.isKeepToolBodies = False
        combineInput.operation = adsk.fusion.FeatureOperations.CutFeatureOperation
        comp.features.combineFeatures.add(combineInput)

        custom_feature.timelineObject.rollTo(False)
        # eventArgs.isValidResult = True
        # _ = des.timeline.movetoNextStep()
        # pass
        # adsk.doEvents()
    except:
        logger.exception('Exception')
        showMessage(f'ExecutePreview: {traceback.format_exc()}\n')       


# Controls what the user can select when the command is running.
# This checks to make sure the point is on a planar face and the
# body the point is on is not an external reference.
@eventHandler(handler_cls = adsk.core.SelectionEventHandler)
def on_preselect_handler(eventArgs: adsk.core.SelectionEventArgs):
    global _des, _root

    des: adsk.fusion.Design = _des
    logger.debug('on_preselect_handler')
    try:
        edge: adsk.fusion.BrepEdge = eventArgs.selection.entity

        if edge is None:
            eventArgs.isSelectable = False
            return

        # Verify the body is not from an XRef.
        if edge.assemblyContext:
            occ = edge.assemblyContext
            if occ.isReferencedComponent:
                eventArgs.isSelectable = False
                return
    except:
        logger.exception('Exception')
        showMessage(f'PreSelectEventHandler: {traceback.format_exc()}\n')


# Event handler to handle the compute of the custom feature.
@eventHandler(handler_cls = adsk.fusion.CustomFeatureEventHandler)
@timelineMarkers
def on_compute_custom_feature(args: adsk.fusion.CustomFeatureEventArgs):
    global _isRolledForEdit
    global _des, _root

    logger.debug('on_compute_custom_feature')

    des: adsk.fusion.Design = _des
    logger.debug(f'1st inside on_compute_custom_feature = {des.timeline.markerPosition}')

    try:
        adsk.doEvents()
        timeline = des.timeline
        markerPosition = timeline.markerPosition
        restoreTL = timeline.item(markerPosition-1)
        
        # Roll the timeline to just before the custom feature being edited.

        # Get the custom feature that is being computed.
        custFeature: adsk.fusion.CustomFeature = args.customFeature
        custFeatTimelineObject = custFeature.timelineObject
        custFeatTimelineObject.rollTo(rollBefore = True)

        # Get the original sketch point and the values from the custom feature.
        edge = custFeature.dependencies.itemById('edge').entity
        radius = custFeature.parameters.itemById('radius').value

        # Create a new temporary body for the pocket. 
        # This can return None when the point isn't on a face.
        covebody = CreateCove(edge, radius)
        if covebody is None:
            # Add a failure status message because it failed to create the pocket.
            args.computeStatus.statusMessages.addError('DRPOINT_COMPUTE_FAILED', '')
            return
        
        # Get the existing base feature and update the body.
        baseFeature: adsk.fusion.BaseFeature = None
        for feature in custFeature.features:
            if feature.objectType == adsk.fusion.BaseFeature.classType():
                baseFeature = feature
                break        

        # Update the body in the base feature.
        baseFeature.startEdit()
        body: adsk.fusion.BRepBody = baseFeature.bodies.item(0)
        baseFeature.updateBody(body, covebody)
        baseFeature.finishEdit()
        restoreTL.rollTo(False)
            
    except:
        logger.exception('Exception')
        showMessage(f'CustomFeatureCompute: {traceback.format_exc()}\n')


# Utility function that given the position and pocket size builds
# a temporary B-Rep body is the tool body to create the pocket.
@timelineMarkers
def CreateCove(edge: adsk.fusion.BRepEdge, radius):
    logger.debug('Creating covebody')
    try:
        if edge is None:
            return None

        # Define the pocket at the origin with the length in the X direction,
        # width in the Y direction, and depth in the -Z direction.
        tBRep: adsk.fusion.TemporaryBRepManager = adsk.fusion.TemporaryBRepManager.get()
        widthDir = adsk.core.Vector3D.create(0, 1, 0)
        startPoint:adsk.fusion.Point3D = None
        endPoint:adsk.fusion.Point3D = None
        face1 = edge.faces.item(0)
        _, startPoint, endPoint = edge.evaluator.getEndPoints()
        
        bodies = []
        bodies.append(tBRep.createCylinderOrCone(startPoint, radius,
                                                endPoint, radius ))                                                

        # Combine the bodies into a single body.
        newBody: adsk.fusion.BRepBody = None
        for body in bodies:
            if newBody is None:
                newBody = body
            else:
                tBRep.booleanOperation(newBody, body, adsk.fusion.BooleanTypes.UnionBooleanType)

        return newBody
    except:
        logger.exception('Exception')
        showMessage(f'CreateCove: {traceback.format_exc()}\n')


# Updates an existing custom pocket feature.
@timelineMarkers
def UpdateCove(customFeature: adsk.fusion.CustomFeature) -> bool:
    logger.debug('UpdateCove')
    # des: adsk.fusion.Design = _app.activeProduct
    try:
        # Get the original edge and radius from the custom feature.
        edge: adsk.fusion.BrepEdge = customFeature.dependencies.itemById('edge').entity

        radius = customFeature.parameters.itemById('radius').value

        # Create a new temporary body for the pocket.
        covebody = CreateCove(edge, radius)
        if covebody is None:
            return False
        
        # Get the existing base feature and update the body.
        baseFeature: adsk.fusion.BaseFeature = list(filter(lambda x: x.objectType == adsk.fusion.BaseFeature.classType(), customFeature.features))[0]
 
        # Update the body in the base feature.
        baseFeature.startEdit()
        body: adsk.fusion.BRepBody = baseFeature.bodies.item(0)
        baseFeature.updateBody(body, covebody)
        baseFeature.finishEdit()

        return True
    except:
        logger.exception('Exception')
        showMessage(f'UpdateFillet: {traceback.format_exc()}\n')
        return False


# Get the face the selected point lies on. This assumes the point is
# in root component space. The returned face will be in the context
# of the root component.
#
# There is a case where more than one face can be found but in this case
# None is returned. The case is when the point is very near the edge of
# the face so it is ambiguous which face the point is on.
def GetFaceUnderPoint(point: adsk.core.Point3D) -> adsk.fusion.BRepFace:
    global _des, _root
    des: adsk.fusion.Design = _des
    root: adsk.fusion.Component = _root

    foundFaces: adsk.core.ObjectCollection = root.findBRepUsingPoint(point, adsk.fusion.BRepEntityTypes.BRepFaceEntityType, 0.01, True)
    if foundFaces.count == 0:
        return None
    face: adsk.fusion.BRepFace = foundFaces.item(0)
    return face

def showMessage(message, error = False):
    textPalette: adsk.core.TextCommandPalette = _ui.palettes.itemById('TextCommands')
    textPalette.writeText(message)

    if error:
        _ui.messageBox(message)