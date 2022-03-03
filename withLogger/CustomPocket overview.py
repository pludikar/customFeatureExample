#Author-Autodesk
#Description-Demonstrates the creation of a custom feature.

from venv import create
import adsk.core, adsk.fusion, traceback

_app: adsk.core.Application = None
_ui: adsk.core.UserInterface = None
_handlers = []

_customFeatureDef: adsk.fusion.CustomFeature = None

_editedCustomFeature: adsk.fusion.CustomFeature = None


def run(context):
    global _app, _ui


    # Create the custom feature definition.
    global _customFeatureDef
    _customFeatureDef = adsk.fusion.CustomFeatureDefinition.create('adskCustomPocket', 
                                                                    'Custom Pocket', 
                                                                    'Resources/CustomPocket')
    _customFeatureDef.editCommandId = 'adskCustomPocketEdit'

    # Connect to the command created event for the create command.
    createCommandCreated = CreatePocketCommandCreatedHandler()
    createCmdDef.commandCreated.add(createCommandCreated)
    _handlers.append(createCommandCreated)

    # Connect to the command created event for the edit command.
    editCommandCreated = EditPocketCommandCreatedHandler()
    editCmdDef.commandCreated.add(editCommandCreated)
    _handlers.append(editCommandCreated)

    # Connect to the compute event for the custom feature.
    computeCustomFeature = ComputeCustomFeature()
    _customFeatureDef.customFeatureCompute.add(computeCustomFeature)
    _handlers.append(computeCustomFeature)



def stop(context):
    # Remove all UI elements.
    pass

# Define the command inputs needed to get the input from the user for the
# creation of the feauture and connect to the command related events.
class CreatePocketCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):  #setup during run()
    def notify(self, args):
        eventArgs = adsk.core.CommandCreatedEventArgs.cast(args)
        cmd = eventArgs.command
        inputs = cmd.commandInputs
        des: adsk.fusion.Design = _app.activeProduct

        global _pointSelectInput, _lengthInput, _widthInput, _depthInput, _radiusInput

        # Create the selection input to select the body(s).
        _pointSelectInput = inputs.addSelectionInput('selectPoint', 
                                                        'Points', 
                                                        'Select point to define pocket position.')
        _pointSelectInput.addSelectionFilter('SketchPoints')
        _pointSelectInput.tooltip = 'Select point to define the center of the pocket.'
        _pointSelectInput.setSelectionLimits(1, 1)

        # Create the value input to get the length.
        length = adsk.core.ValueInput.createByReal(5)
        lengthUnits = des.unitsManager.defaultLengthUnits
        _lengthInput = inputs.addValueInput('length', 'Length', lengthUnits, length)

        # Create the value input to get the width.
        width = adsk.core.ValueInput.createByReal(3)
        _widthInput = inputs.addValueInput('width', 'Width', lengthUnits, width)

        # Create the value input to get the depth.
        depth = adsk.core.ValueInput.createByReal(1)
        _depthInput = inputs.addValueInput('depth', 'Depth', lengthUnits, depth)

        # Create the value input to get the fillet radius.
        radius = adsk.core.ValueInput.createByReal(0.5)
        _radiusInput = inputs.addValueInput('cornerRadius', 'Corner Radius', lengthUnits, radius)
                                            
        # Connect to the needed command related events.
        onExecutePreview = ExecutePreviewHandler() #std execute preview event
        cmd.executePreview.add(onExecutePreview)
        _handlers.append(onExecutePreview)

        onExecute = CreateExecuteHandler() #std command event
        cmd.execute.add(onExecute)
        _handlers.append(onExecute)  

        onPreSelect = PreSelectHandler() #std preselect event
        cmd.preSelect.add(onPreSelect)
        _handlers.append(onPreSelect)

        onValidate = ValidateInputsHandler() #std validation event
        cmd.validateInputs.add(onValidate)
        _handlers.append(onValidate)

# Event handler for the validateInputs event.
class ValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        eventArgs = adsk.core.ValidateInputsEventArgs.cast(args)

        # Verify the inputs have valid expressions.
        if not all( [_lengthInput.isValidExpression, _widthInput.isValidExpression,
                    _depthInput.isValidExpression, _radiusInput.isValidExpression] ):
            eventArgs.areInputsValid = False
            return

        # Verify the sizes are valid.
        diam = _radiusInput.value * 2
        if diam + 0.01 > _lengthInput.value or diam + 0.01 > _widthInput.value:
            eventArgs.areInputsValid = False
            return

        
# Event handler for the execute event of the create command.
class CreateExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        custFeatInput = comp.features.customFeatures.createInput(_customFeatureDef)

        lengthInput = adsk.core.ValueInput.createByString(_lengthInput.expression)
        custFeatInput.addCustomParameter('length', 'Length', lengthInput,
                                            defLengthUnits, True)
        widthInput = adsk.core.ValueInput.createByString(_widthInput.expression)               
        custFeatInput.addCustomParameter('width', 'Width', widthInput,
                                            defLengthUnits, True)  
        depthInput = adsk.core.ValueInput.createByString(_depthInput.expression)             
        custFeatInput.addCustomParameter('depth', 'Depth', depthInput,
                                            defLengthUnits, True) 
        radiusInput = adsk.core.ValueInput.createByString(_radiusInput.expression)             
        custFeatInput.addCustomParameter('radius', 'Radius', radiusInput,
                                            defLengthUnits, True)               

        custFeatInput.addDependency('point', skPoint)

        # custFeatInput.setStartAndEndFeatures(baseFeat, combineFeature)
        comp.features.customFeatures.add(custFeatInput)


class EditPocketCommandCreatedHandler(adsk.core.CommandCreatedEventHandler):  # set up during run() 
    def notify(self, args):
        global _editedCustomFeature
        _editedCustomFeature = _ui.activeSelections.item(0).entity
        if _editedCustomFeature is None:
            return

        global _pointSelectInput, _lengthInput, _widthInput, _depthInput, _radiusInput

        # Create the selection input to select the sketch point.

        # Get the collection of custom parameters for this custom feature.
        params = _editedCustomFeature.parameters

        # Create the value input to get the length.
        length = adsk.core.ValueInput.createByString(params.itemById('length').expression)
        _lengthInput = inputs.addValueInput('length', 'Length', defLengthUnits, length)

        # Create the value input to get the width.
        width = adsk.core.ValueInput.createByString(params.itemById('width').expression)
        _widthInput = inputs.addValueInput('width', 'Width', defLengthUnits, width)

        # Create the value input to get the depth.
        depth = adsk.core.ValueInput.createByString(params.itemById('depth').expression)
        _depthInput = inputs.addValueInput('depth', 'Depth', defLengthUnits, depth)

        # Create the value input to get the fillet radius.
        radius = adsk.core.ValueInput.createByString(params.itemById('radius').expression)
        _radiusInput = inputs.addValueInput('cornerRadius', 'Corner Radius', defLengthUnits, radius)
                                            
        # Connect to the needed command related events.
        onExecutePreview = ExecutePreviewHandler() #std execute preview event
        cmd.executePreview.add(onExecutePreview)
        _handlers.append(onExecutePreview)

        onExecute = EditExecuteHandler() #std execute event
        cmd.execute.add(onExecute)
        _handlers.append(onExecute)  

        onPreSelect = PreSelectHandler() # std preselect event
        cmd.preSelect.add(onPreSelect)
        _handlers.append(onPreSelect)

        onActivate = EditActivateHandler() #std command event
        cmd.activate.add(onActivate)
        _handlers.append(onActivate)

        onValidate = ValidateInputsHandler() #std validation event
        cmd.validateInputs.add(onValidate)
        _handlers.append(onValidate)


# Event handler for the activate event.
class EditActivateHandler(adsk.core.CommandEventHandler):  #setup by command create
    def notify(self, args):
        # Roll the timeline to just before the custom feature being edited.
        _editedCustomFeature.timelineObject.rollTo(rollBefore = True)
        _isRolledForEdit = True

        # Define a transaction marker so the the roll is not aborted with each change.
        eventArgs.command.beginStep()

        # Get the point and add it to the selection input.
        skPoint = _editedCustomFeature.dependencies.itemById('point').entity
        _pointSelectInput.addSelection(skPoint)
 

# Event handler for the execute event of the edit command.
class EditExecuteHandler(adsk.core.CommandEventHandler):   #setup by command create
    def notify(self, args):
        global _editedCustomFeature
        # Update the parameters.
        params = _editedCustomFeature.parameters
        lengthParam = params.itemById('length')
        lengthParam.expression = _lengthInput.expression
        widthParam = params.itemById('width')
        widthParam.expression = _widthInput.expression
        depthParam = params.itemById('depth')
        depthParam.expression = _depthInput.expression
        radiusParam = params.itemById('radius')
        radiusParam.expression = _radiusInput.expression

        # Update the feature.
        UpdatePocket(_editedCustomFeature)

        # Update the point dependency.
        dependency = _editedCustomFeature.dependencies.itemById('point')
        dependency.entity = point

        # Roll the timeline to its previous position.

        _editedCustomFeature = None

 

# Event handler for the executePreview event.
class ExecutePreviewHandler(adsk.core.CommandEventHandler):   #setup by command create
    def notify(self, args):
        eventArgs = adsk.core.CommandEventArgs.cast(args)        

        # Get the settings from the inputs.
        skPoint: adsk.fusion.SketchPoint = _pointSelectInput.selection(0).entity
        length = _lengthInput.value
        width = _widthInput.value
        depth = _depthInput.value
        radius = _radiusInput.value

        # Create the fillet feature.
        pocketBody = CreatePocketBody(skPoint.worldGeometry, length, width, depth, radius)

        # Create a base feature and add the body.
        # Create a combine feature to subtract the pocket body from the part.
 

# Controls what the user can select when the command is running.
# This checks to make sure the point is on a planar face and the
# body the point is on is not an external reference.
class PreSelectHandler(adsk.core.SelectionEventHandler):   #setup by command create
    def notify(self, args):
        eventArgs = adsk.core.SelectionEventArgs.cast(args)
        preSelectPoint: adsk.fusion.SketchPoint = eventArgs.selection.entity

        face = GetFaceUnderPoint(preSelectPoint.worldGeometry)
        if face is None:
            eventArgs.isSelectable = False
            return

        # Verify the body is not from an XRef.
        if preSelectPoint.assemblyContext:
            occ = preSelectPoint.assemblyContext
            if occ.isReferencedComponent:
                eventArgs.isSelectable = False
                return


# Event handler to handle the compute of the custom feature.
class ComputeCustomFeature(adsk.fusion.CustomFeatureEventHandler):
    def notify(self, args):
        eventArgs: adsk.fusion.CustomFeatureEventArgs = args

        # Get the custom feature that is being computed.
        custFeature = eventArgs.customFeature

        # Get the original sketch point and the values from the custom feature.
        skPoint = custFeature.dependencies.itemById('point').entity
        length = custFeature.parameters.itemById('length').value
        width = custFeature.parameters.itemById('width').value
        depth = custFeature.parameters.itemById('depth').value
        radius = custFeature.parameters.itemById('radius').value

        # Create a new temporary body for the pocket. 
        # This can return None when the point isn't on a face.
        pocketBody = CreatePocketBody(skPoint.worldGeometry, length, 
                                        width, depth, radius)
        if pocketBody is None:
            # Add a failure status message because it failed to create the pocket.
            eventArgs.computeStatus.statusMessages.addError('DRPOINT_COMPUTE_FAILED', '')
            return
        
        # Get the existing base feature and update the body.

        # Update the body in the base feature.
 

# Utility function that given the position and pocket size builds
# a temporary B-Rep body is the tool body to create the pocket.
def CreatePocketBody(point, length, width, depth, radius):
    # Get the face the point is on.
    face: adsk.fusion.BRepFace = GetFaceUnderPoint(point)
    if face is None:
        return None

    # Define the pocket at the origin with the length in the X direction,
    # width in the Y direction, and depth in the -Z direction.
    tBRep: adsk.fusion.TemporaryBRepManager = adsk.fusion.TemporaryBRepManager.get()
    lengthDir = adsk.core.Vector3D.create(1, 0, 0)
    widthDir = adsk.core.Vector3D.create(0, 1, 0)
    bodies = []
    lengthBox = adsk.core.OrientedBoundingBox3D.create(adsk.core.Point3D.create(0, 0, -depth / 2),
                                                        lengthDir, widthDir, length, width - (radius * 2), depth)
    bodies.append(tBRep.createBox(lengthBox))

    widthBox = adsk.core.OrientedBoundingBox3D.create(adsk.core.Point3D.create(0, 0, -depth / 2),
                                                        lengthDir, widthDir, length - (radius *2), width, depth)
    bodies.append(tBRep.createBox(widthBox))
    
    bodies.append(tBRep.createCylinderOrCone(adsk.core.Point3D.create((length / 2) - radius, (width / 2) - radius, 0), radius,
                                                adsk.core.Point3D.create((length / 2) - radius, (width / 2) - radius, -depth), radius))                                                
    bodies.append(tBRep.createCylinderOrCone(adsk.core.Point3D.create((length / 2) - radius, (-width / 2) + radius, 0), radius,
                                                adsk.core.Point3D.create((length / 2) - radius, (-width / 2) + radius, -depth), radius))
    bodies.append(tBRep.createCylinderOrCone(adsk.core.Point3D.create((-length / 2) + radius, (width / 2) - radius, 0), radius,
                                                adsk.core.Point3D.create((-length / 2) + radius, (width / 2) - radius, -depth), radius))
    bodies.append(tBRep.createCylinderOrCone(adsk.core.Point3D.create((-length / 2) + radius, (-width / 2) + radius, 0), radius,
                                                adsk.core.Point3D.create((-length / 2) + radius, (-width / 2) + radius, -depth), radius))

    # Combine the bodies into a single body.

    # Get the natural U direction and normal of the face and use them as the length and depth directions.
    eval = face.evaluator
    (_, param) = eval.getParameterAtPoint(point)

    # Define a transform to position the pocket body onto the part.
  

# Updates an existing custom pocket feature.
def UpdatePocket(customFeature: adsk.fusion.CustomFeature) -> bool:
    # Get the original sketch point and the values from the custom feature.
    skPoint: adsk.fusion.SketchPoint = customFeature.dependencies.itemById('point').entity
    length = customFeature.parameters.itemById('length').value
    width = customFeature.parameters.itemById('width').value
    depth = customFeature.parameters.itemById('depth').value
    radius = customFeature.parameters.itemById('radius').value

    # Create a new temporary body for the pocket. This can return None when the point isn't on a face.
    # Get the existing base feature and update the body.
    # Update the body in the base feature.
  

# Get the face the selected point lies on. This assumes the point is
# in root component space. The returned face will be in the context
# of the root component.
#
# There is a case where more than one face can be found but in this case
# None is returned. The case is when the point is very near the edge of
# the face so it is ambiguous which face the point is on.
def GetFaceUnderPoint(point: adsk.core.Point3D) -> adsk.fusion.BRepFace:
    des: adsk.fusion.Design = _app.activeProduct
    root = des.rootComponent

    foundFaces: adsk.core.ObjectCollection = root.findBRepUsingPoint(point, adsk.fusion.BRepEntityTypes.BRepFaceEntityType, 0.01, True)
    if foundFaces.count == 0:
        return None
    else:
        face: adsk.fusion.BRepFace = foundFaces.item(0)
        return face

    return None


def showMessage(message, error = False):
    textPalette: adsk.core.TextCommandPalette = _ui.palettes.itemById('TextCommands')
    textPalette.writeText(message)

    if error:
        _ui.messageBox(message)