"""Execute selected unmodified official functions on tiny synthetic inputs; no torch/model."""
import importlib.util,pathlib,json,inspect,math
import numpy as np
import pandas as pd
import scipy
root=pathlib.Path(__file__).resolve().parents[1]
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,root/path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
metrics=module('official_metrics','code/src_safety_evaluation/validation_utils/utils_eval_metrics.py')
coor=module('official_coor','code/src_data_preparation/represent_utils/coortrans.py')
r={}
r['versions']={'numpy':np.__version__,'pandas':pd.__version__,'scipy':scipy.__version__}
r['partial_auc']={'exact_v5':.575,'official_1000_grid':float(metrics.partial_auc([0,.1,.3,1],[0,.8,.9,1],.8))}
assert abs(r['partial_auc']['official_1000_grid']-.575)<1e-4
x,y=coor.coortrans().rotate_coor(3.,4.,6.,8.)
r['coordinate_rotation']={'axis':[3,4],'displacement':[6,8],'output':[float(x),float(y)],'expected':[0,10]};assert abs(x)<1e-12 and abs(y-10)<1e-12
# Two event rows: one TP with a 2s warning; one FN with a short warning 8s before impact.
w=pd.DataFrame({'threshold':[1.,1.],'impact_time':[10.,10.],'warning_timestamp':[8000.,2000.],'true_warning':[1,0]})
f1=pd.Series([.6],index=[1.])
a,b=metrics.get_time(w,f1=f1)
r['tti_counterexample']={'true_warning':[1,0],'TTI':[2,8],'official_median':float(a[0]),'TP_only_median':2.}
assert a[0]==5
r['CI_default_alpha']={'low_wrapper':inspect.signature(metrics.get_low_CI).parameters['alpha'].default,'upper_wrapper':inspect.signature(metrics.get_up_CI).parameters['alpha'].default,'base':inspect.signature(metrics._median_ci_bounds).parameters['alpha'].default}
(root/'checks/official-function-results.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
