# ; -*- mode: Python;-*-
from modelUtils.distanceDelays import makeDelayedLaterals
#JABALERT: Should update the docstring once the GCA paper has been
# accepted or at least submitted.
"""
GCAL

Work in progress on an improved version of the LISSOM orientation map
simulation from figure 5.9 of Miikkulainen, Bednar, Choe, and Sirosh
(2005), Computational Maps in the Visual Cortex, Springer.  Important
differences include:

 - Using divisive normalization to the LGN to provide contrast gain control (GC)
   and contrast-invariant tuning
 - Using homeostatic adaptation (A) rather than manual threshold adjustment,
   to avoid the need for most parameter adjustment and to be more robust
 - Using a fixed lateral excitatory radius rather than shrinking it
   (now that homeostatic plasticity allows all neurons to develop robustly) 

$Id$
"""
__version__='$Revision$'

from math import pi

import numpy, sys, os, pickle
import param

from topo import learningfn,numbergen,transferfn,pattern,projection,responsefn,sheet

import topo.learningfn.optimized
import topo.learningfn.projfn 
import topo.transferfn.optimized 
import topo.pattern.random
import topo.pattern.image
import topo.responsefn.optimized 
import topo.sheet.lissom
import topo.sheet.optimized

import topo.transferfn.misc
from topo.base.arrayutil import DivideWithConstant
import topo.analysis.featureresponses

# Parameters that can be passed on the command line using -p
from topo.misc.commandline import global_params as p

def makeParams():
    p.add(

        dataset=param.ObjectSelector(default='Gaussian',objects=
                                     ['Gaussian','Nature'],doc="""
        Set of input patterns to use::

          :'Gaussian': Two-dimensional Gaussians
          :'Nature':   Shouval's 1999 monochrome 256x256 images"""),

        num_inputs=param.Integer(default=2,bounds=(1,None),doc="""
        How many input patterns to present per unit area at each
        iteration, when using discrete patterns (e.g. Gaussians)."""),
        
        area=param.Number(default=1.0,bounds=(0,None),
                          inclusive_bounds=(False,True),doc="""
        Linear size of cortical area to simulate.
        2.0 gives a 2.0x2.0 Sheet area in V1."""),
        
        retina_density=param.Number(default=24.0,bounds=(0,None),
                                    inclusive_bounds=(False,True),doc="""
        The nominal_density to use for the retina."""),
        
        lgn_density=param.Number(default=24.0,bounds=(0,None),
                                 inclusive_bounds=(False,True),doc="""
        The nominal_density to use for the LGN."""),
        
        cortex_density=param.Number(default=48.0,bounds=(0,None),
                                    inclusive_bounds=(False,True),doc="""
        The nominal_density to use for V1."""),
        
        scale=param.Number(default=0.7,inclusive_bounds=(False,True),doc="""
        Brightness of the input patterns"""),
        
        aff_strength=param.Number(default=1.5,bounds=(0.0,None),doc="""
        Overall strength of the afferent projection to V1."""),

        exc_strength=param.Number(default=1.7,bounds=(0.0,None),doc="""
        Overall strength of the lateral excitatory projection to V1."""),
        
        inh_strength=param.Number(default=1.4,bounds=(0.0,None),doc="""
        Overall strength of the lateral inhibitory projection to V1."""),
        
        aff_lr=param.Number(default=0.1,bounds=(0.0,None),doc="""
        Learning rate for the afferent projection to V1."""),
        
        exc_lr=param.Number(default=0.0,bounds=(0.0,None),doc="""
        Learning rate for the lateral excitatory projection to V1."""),
        
        inh_lr=param.Number(default=0.3,bounds=(0.0,None),doc="""
        Learning rate for the lateral inhibitory projection to V1."""))
    
    return p
    



def makeSheets(p):

### Specify weight initialization, response function, and learning function
    projection.CFProjection.cf_shape=pattern.Disk(smoothing=0.0)
    projection.CFProjection.response_fn=responsefn.optimized.CFPRF_DotProduct_opt()
    projection.CFProjection.learning_fn=learningfn.optimized.CFPLF_Hebbian_opt()
    projection.CFProjection.weights_output_fns=[transferfn.optimized.CFPOF_DivisiveNormalizeL1_opt()]
    projection.SharedWeightCFProjection.response_fn=responsefn.optimized.CFPRF_DotProduct_opt()

    combined_inputs = GCALStimulusPattern(p, "Gaussian")


    topo.sim['Retina']=sheet.GeneratorSheet(nominal_density=p.retina_density,
                                            input_generator=combined_inputs, period=1.0, phase=0.05,
                                            nominal_bounds=sheet.BoundingBox(radius=p.area/2.0+0.25+0.375+0.5))

    # LGN has lateral connections for divisive normalization
    for s in ['LGNOn','LGNOff']:
        topo.sim[s]=sheet.optimized.LISSOM_Opt(nominal_density=p.lgn_density,
                                               nominal_bounds=sheet.BoundingBox(radius=p.area/2.0+0.25+0.5),
                                               output_fns=[transferfn.misc.HalfRectify()],
                                               tsettle=2,strict_tsettle=1,measure_maps=False)


    topo.sim['V1'] = sheet.lissom.LISSOM(nominal_density=p.cortex_density,
                                         tsettle=16, plastic=True, 
                                         nominal_bounds=sheet.BoundingBox(radius=p.area/2.0),
                                         output_fns=[transferfn.misc.HomeostaticResponse()])

    topo.sim['V1'].joint_norm_fn=topo.sheet.optimized.compute_joint_norm_totals_opt
    
    return combined_inputs


def GCALStimulusPattern(p, patType="Gaussian"):
    
    if patType != p.dataset: print "*WARNING*: Pattern class mismatch for GCAL"

    if p.dataset=="Gaussian":
        input_type=pattern.Gaussian
        total_num_inputs=int(p.num_inputs*p.area*p.area)
        inputs=[input_type(x=numbergen.UniformRandom(lbound=-(p.area/2.0+0.25),
                                                     ubound= (p.area/2.0+0.25),seed=12+i),
                           y=numbergen.UniformRandom(lbound=-(p.area/2.0+0.25),
                                                     ubound= (p.area/2.0+0.25),seed=35+i),
                           orientation=numbergen.UniformRandom(lbound=-pi,ubound=pi,seed=21+i),
                           # CEBALERT: is this used?
                           bounds=sheet.BoundingBox(radius=1.125),
                           size=0.088388, aspect_ratio=4.66667, scale=p.scale)
                for i in xrange(total_num_inputs)]

        combined_inputs = pattern.SeparatedComposite(min_separation=0,generators=inputs)
        
    elif p.dataset=="Nature":
        input_type=pattern.image.FileImage
        image_filenames=["images/shouval/combined%02d.png"%(i+1) for i in xrange(25)]
        inputs=[input_type(filename=f,
                           size=10.0,  #size_normalization='original',(size=10.0)
                           x=numbergen.UniformRandom(lbound=-0.75,ubound=0.75,seed=12),
                           y=numbergen.UniformRandom(lbound=-0.75,ubound=0.75,seed=36),
                           orientation=numbergen.UniformRandom(lbound=-pi,ubound=pi,seed=65))
                for f in image_filenames]

        combined_inputs =pattern.Selector(generators=inputs)

    return combined_inputs

### Connections
def connectLGNLaterals(LGNRingNo, PLOT):

    boundsChangeList = []
    # LGN has lateral connections for divisive normalization
    for s in ['LGNOn','LGNOff']:

        lgn_surroundg = pattern.Gaussian(size=0.25,aspect_ratio=1.0,
                                         output_fns=[transferfn.DivisiveNormalizeL1()])

        connectionParams = {'delay':0.05, 'name':'LateralGC',                       
                            'dest_port':('Activity'), 'activity_group':(0.6,DivideWithConstant(c=0.11)),
                            'connection_type': projection.SharedWeightCFProjection,
                            'strength':0.6, 'weights_generator':lgn_surroundg,
                            'nominal_bounds_template':sheet.BoundingBox(radius=0.25)}

        boundsChanged = makeDelayedLaterals(s, ('GC%s' % s), connectionParams, LGNRingNo,
                                            pattern.Gaussian, {'size':0.25,'aspect_ratio':1.0,
                                                               'output_fns':[transferfn.DivisiveNormalizeL1()]} )
    boundsChangeList.append(boundsChanged)
    return boundsChangeList


def connectFeedForward(p):

    # Components of DoG weights for the LGN
    centerg   = pattern.Gaussian(size=0.07385,aspect_ratio=1.0,
                                 output_fns=[transferfn.DivisiveNormalizeL1()])
    surroundg = pattern.Gaussian(size=0.29540,aspect_ratio=1.0,
                                 output_fns=[transferfn.DivisiveNormalizeL1()])
    # DoG weights for the LGN (center surround on and off)
    on_weights = pattern.Composite(
        generators=[centerg,surroundg],operator=numpy.subtract)

    off_weights = pattern.Composite(
        generators=[surroundg,centerg],operator=numpy.subtract)


    topo.sim.connect(
        'Retina','LGNOn',delay=0.05,strength=2.33,name='AfferentToLGNOn',
        connection_type=projection.SharedWeightCFProjection,
        nominal_bounds_template=sheet.BoundingBox(radius=0.375),
        weights_generator=on_weights)

    topo.sim.connect(
        'Retina','LGNOff',delay=0.05,strength=2.33,name='AfferentToLGNOff',
        connection_type=projection.SharedWeightCFProjection,
        nominal_bounds_template=sheet.BoundingBox(radius=0.375),
        weights_generator=off_weights)

    topo.sim.connect(
        'LGNOn','V1',delay=0.05,strength=p.aff_strength,name='LGNOnAfferent',
        dest_port=('Activity','JointNormalize','Afferent'),
        connection_type=projection.CFProjection,learning_rate=p.aff_lr,
        nominal_bounds_template=sheet.BoundingBox(radius=0.27083),
        weights_generator=pattern.random.GaussianCloud(gaussian_size=2*0.27083),
        learning_fn=learningfn.optimized.CFPLF_Hebbian_opt())
                     
    topo.sim.connect(
        'LGNOff','V1',delay=0.05,strength=p.aff_strength,name='LGNOffAfferent',
        dest_port=('Activity','JointNormalize','Afferent'),
        connection_type=projection.CFProjection,learning_rate=p.aff_lr,
        nominal_bounds_template=sheet.BoundingBox(radius=0.27083),
        weights_generator=pattern.random.GaussianCloud(gaussian_size=2*0.27083),
        learning_fn=learningfn.optimized.CFPLF_Hebbian_opt())


def connectV1Laterals(p,V1RingNo): 

    ######################################################################################
    # <<<<<WARNING>>>>: CANNOT CHANGE BOUNDS AND SIZE IN CONNECTIONS POST-INITIALISATION #
    ######################################################################################

    if V1RingNo not in [1, 'MAX']: print "**WARNING**: COUPLED RING COUNT FOR V1 LATERAL INH and EXC"

    # topo.sim.connect(
    #     'V1','V1',delay=0.05,strength=p.exc_strength,name='LateralExcitatory',
    #     connection_type=projection.CFProjection,learning_rate=p.exc_lr,
    #     nominal_bounds_template=sheet.BoundingBox(radius=0.104),
    #     weights_generator=pattern.Gaussian(aspect_ratio=1.0, size=0.05))

    V1ExcParams = {'delay':0.05, 'strength':p.exc_strength, 'name':'LateralExcitatory',
                   'connection_type':projection.CFProjection, 'learning_rate':p.exc_lr,
                   'nominal_bounds_template':sheet.BoundingBox(radius=0.104),
                   'weights_generator':pattern.Gaussian(aspect_ratio=1.0, size=0.05)}

    V1ExcBoundsChanged = makeDelayedLaterals('V1', 'LateralExcitatory', V1ExcParams, V1RingNo,
                                        pattern.Gaussian, {'aspect_ratio':1.0, 'size':0.05})


    # topo.sim.connect(
    #     'V1','V1',delay=0.05,strength=-1.0*p.inh_strength,name='LateralInhibitory',
    #     connection_type=projection.CFProjection,learning_rate=p.inh_lr,
    #     nominal_bounds_template=sheet.BoundingBox(radius=0.22917),
    #     weights_generator=pattern.random.GaussianCloud(gaussian_size=0.15))


    V1InhParams = {'delay':0.05, 'strength':-1.0*p.inh_strength, 'name':'LateralInhibitory',
                   'connection_type':projection.CFProjection,'learning_rate':p.inh_lr,
                   'nominal_bounds_template':sheet.BoundingBox(radius=0.22917),
                   'weights_generator':pattern.random.GaussianCloud(gaussian_size=0.15)}

    V1InhBoundsChanged = makeDelayedLaterals('V1', 'LateralInhibitory' , V1InhParams, V1RingNo,
                                             pattern.random.GaussianCloud, {'gaussian_size':0.15})

    return [V1ExcBoundsChanged, V1InhBoundsChanged]



def config():
    # Default locations for model editor
    topo.sim.grid_layout([[None,    'V1',     None],
                          ['LGNOn', None,     'LGNOff'],
                          [None,    'Retina', None]], xstart=150,item_scale=0.8)

    # Set up appropriate defaults for analysis
    topo.analysis.featureresponses.FeatureMaps.selectivity_multiplier=2.0
    topo.analysis.featureresponses.FeatureCurveCommand.apply_output_fns=True
    topo.analysis.featureresponses.FeatureCurveCommand.curve_parameters=[{"contrast":1},
                                                                         {"contrast":10}, 
                                                                         {"contrast":30}, 
                                                                         {"contrast":50}, 
                                                                         {"contrast":100}]

def connectGCAL(p, LGNRingNo='MAX', V1RingNo='MAX',PLOT=True):

    print "Connecting GCAL with %s LGN rings and %s V1 rings" % (str(LGNRingNo),str(V1RingNo))
    LGNChangeList = connectLGNLaterals(LGNRingNo, PLOT)
    connectFeedForward(p)
    V1ChangeList = connectV1Laterals(p,V1RingNo)
    config()

    if True in (LGNChangeList+V1ChangeList): print "Bounds for a delay connection changed. Exiting.";sys.exit()


if __name__ == '__main__':
    p =makeParams()
    makeSheets(p)
    connectGCAL(p, LGNRingNo=1, V1RingNo='MAX', PLOT=False)
    config()

    