import torch 
import numpy as np 
from bisect import bisect_right


def clip_gradient(optimizer, grad_clip):
    for group in optimizer.param_groups:
        for param in group['params']:
            if param.grad is not None:
                param.grad.data.clamp_(-grad_clip, grad_clip)


def save_checkpoint(epoch, model_rpn, model_classifier, optimizer_model_rpn, optimizer_classifier, name="_"):
    state = {'model_rpn': model_rpn,
             'model_classifier': model_classifier,
             'optimizer_model_rpn': optimizer_model_rpn,
             'optimizer_classifier': optimizer_classifier, 
             'epoch': epoch
             }

    filename = name + 'checkpoint_ssd300.pth.tar'
    # # torch.save(state, filename)
    # # If this checkpoint is the best so far, store a copy so it doesn't get overwritten by a worse checkpoint
    # if is_best:
    #     torch.save(state, 'BEST_' + filename)


# def save_checkpoint(state, is_best, fpath='checkpoint.pth.tar'):
#     mkdir_if_missing(osp.dirname(fpath))
#     matching_file = fpath.split("ep")[0].split("/")[-1]
#     dir_ =  osp.dirname(fpath)
#     for f in os.listdir(dir_):
#         if re.search(matching_file, f):
#             os.remove(os.path.join(dir_, f))            
#     torch.save(state, fpath)


def tile(a, dim, n_tile,device='cpu'):
    init_dim = a.size(dim)
    repeat_idx = [1] * a.dim()
    repeat_idx[dim] = n_tile
    a = a.repeat(*(repeat_idx))
    order_index = torch.LongTensor(np.concatenate([init_dim * np.arange(n_tile) + i for i in range(init_dim)])).to(device=device)
    return torch.index_select(a, dim, order_index)


def iou(a, b):
    # (xmin,ymin,xmax,ymax)
    # invlaid boxes
    if a[0] >= a[2] or a[1] >= a[3] or b[0] >= b[2] or b[1] >= b[3]:
        return 0.0

    #intersection 
    x1 = max(a[0], b[0])
    y1 = max(a[1], b[1])
    x2 = min(a[2], b[2])
    y2 = min(a[3], b[3])

    if x2 - x1 <= 0  or y2 - y1 <=0 :
        intersection = 0 
    else:
        intersection = (x2 - x1) * (y2 - y1)

    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union =  area_a + area_b - intersection

    if union <= 0 : 
        return 0.0
    else:
        return float(intersection) / float(union + 1e-6)




def iou_tensor(x1, y1, x2, y2, boxes):
        
    main_ind = torch.arange(0 , boxes.size(0))

    area_1 = (x2 - x1) * (y2 - y1)

    x11 = torch.max(boxes[:,0] , x1)
    y11 = torch.max(boxes[:,1] , y1)
    x22 = torch.min(boxes[:,2] , x2)
    y22 = torch.min(boxes[:,3] , y2)

    intersection = (x22 - x11) * (y22 - y11)
    ind = x22 - x11 > 0 

    intersection = intersection[ind]
    y22 = y22[ind]
    y11 = y11[ind]
    x22 = x22[ind]
    x11 = x11[ind]
    boxes = boxes[ind]
    main_ind = main_ind[ind]


    if intersection.size(0) == 0 : 
        return 0 , -1

    ind = y22 - y11 > 0

    intersection = intersection[ind]
    y22 = y22[ind]
    y11 = y11[ind]
    x22 = x22[ind]
    x11 = x11[ind]
    boxes = boxes[ind]
    main_ind = main_ind[ind]

    if intersection.size(0) == 0 : 
        return 0 , -1


    area_2 = (boxes[:,2] -  boxes[:,0]) * (boxes[:,3] -  boxes[:,1])

    union = area_1 + area_2 - intersection

    ind = union > 0
    union = union[ ind ]
    intersection = intersection[ ind ]
    main_ind = main_ind[ind]

    if intersection.size(0) == 0 : 
        return 0 , -1


    iou = intersection / (union + 1e-6)
    _, ind = iou.sort()
    
    return  iou[ind[-1]] , main_ind[ind[-1]]




class WarmupMultiStepLR(torch.optim.lr_scheduler._LRScheduler):
    def __init__(self, optimizer, milestones, gamma=0.1, warmup_factor=1.0 / 3, warmup_iters=500, warmup_method="linear", last_epoch=-1):
        if not list(milestones) == sorted(milestones):
            raise ValueError(
                "Milestones should be a list of" " increasing integers. Got {}",
                milestones,
            )
        if warmup_method not in ("constant", "linear"):
            raise ValueError(
                "Only 'constant' or 'linear' warmup_method accepted"
                "got {}".format(warmup_method)
            )
        self.milestones = milestones
        self.gamma = gamma
        self.warmup_factor = warmup_factor
        self.warmup_iters = warmup_iters
        self.warmup_method = warmup_method
        super(WarmupMultiStepLR, self).__init__(optimizer, last_epoch)
  
    def get_lr(self):
        warmup_factor = 1
        if self.last_epoch < self.warmup_iters:
            if self.warmup_method == "constant":
                warmup_factor = self.warmup_factor
            elif self.warmup_method == "linear":
                alpha = float(self.last_epoch) / float(self.warmup_iters)
                warmup_factor = self.warmup_factor * (1 - alpha) + alpha
        return [
            base_lr
            * warmup_factor
            * self.gamma ** bisect_right(self.milestones, self.last_epoch)
            for base_lr in self.base_lrs
        ]
