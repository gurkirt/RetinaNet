

""" FPN network Classes

Author: Gurkirt Singh
Inspired from https://github.com/kuangliu/pytorch-retinanet and
https://github.com/gurkirt/realtime-action-detection

"""

from models.backbone_models import backbone_models
import torch, math, pdb, math
import torch.nn as nn

class RetinaNet(nn.Module):
    """Feature Pyramid Network Architecture
    The network is composed of a backbone FPN network followed by the
    added Head conv layers.  
    Each head layer branches into
        1) conv2d for class conf scores
        2) conv2d for localization predictions

    See: 
    RetinaNet: https://arxiv.org/pdf/1708.02002.pdf for more details.
    FPN: https://arxiv.org/pdf/1612.03144.pdf

    Args:
        backbone Network:
        Program Argument Namespace

    """

    def __init__(self, backbone, args):
        super(RetinaNet, self).__init__()

        self.num_classes = args.num_classes
        # TODO: implement __call__ in anchorBox
        self.ar = args.ar
        self.use_bias = args.use_bias
        self.head_size = args.head_size
        self.backbone_net = backbone
        self.shared_heads = args.shared_heads
        self.num_head_layers = args.num_head_layers
        assert self.shared_heads<self.num_head_layers, 'number of head layers should be less than shared layers h:'+str(self.num_head_layers)+' sh:'+str(self.shared_heads)
        if self.shared_heads>0:
            self.features_layers = self.make_features(self.shared_heads)
        self.reg_heads = self.make_head(self.ar * 4, self.num_head_layers - self.shared_heads)
        self.cls_heads = self.make_head(self.ar * self.num_classes, self.num_head_layers - self.shared_heads)
        
        if args.loss_type != 'mbox':
            self.prior_prob = 0.01
            bias_value = -math.log((1 - self.prior_prob ) / self.prior_prob )
            nn.init.constant_(self.cls_heads[-1].bias, bias_value)


    def forward(self, x, get_features=False):
        sources = self.backbone_net(x)
        features = list()
        # pdb.set_trace()
        if self.shared_heads>0:
            for x in sources:
                features.append(self.features_layers(x))
        else:
            features = sources
        loc = list()
        conf = list()
        for x in features:
            loc.append(self.reg_heads(x).permute(0, 2, 3, 1).contiguous())
            conf.append(self.cls_heads(x).permute(0, 2, 3, 1).contiguous())

        loc = torch.cat([o.view(o.size(0), -1) for o in loc], 1)
        conf = torch.cat([o.view(o.size(0), -1) for o in conf], 1)
        
        if get_features:
            return loc.view(loc.size(0), -1, 4), conf.view(conf.size(0), -1, self.num_classes), features
        else:
            return loc.view(loc.size(0), -1, 4), conf.view(conf.size(0), -1, self.num_classes)


    def make_features(self,  shared_heads):
        layers = []
        use_bias =  self.use_bias
        head_size = self.head_size
        for _ in range(shared_heads):
            layers.append(nn.Conv2d(head_size, head_size, kernel_size=3, stride=1, padding=1, bias=use_bias))
            layers.append(nn.ReLU(True))
        
        layers = nn.Sequential(*layers)
        
        for m in layers.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.normal_(m.weight, mean=0, std=0.01)
                if hasattr(m.bias, 'data'):
                    nn.init.constant_(m.bias, 0)

        return layers

    def make_head(self, out_planes, nun_shared_heads):
        layers = []
        use_bias =  self.use_bias
        head_size = self.head_size
        for _ in range(nun_shared_heads):
            layers.append(nn.Conv2d(head_size, head_size, kernel_size=3, stride=1, padding=1, bias=use_bias))
            layers.append(nn.ReLU(True))

        layers.append(nn.Conv2d(head_size, out_planes, kernel_size=3, stride=1, padding=1))
        layers = nn.Sequential(*layers)
        
        for m in layers.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.normal_(m.weight, mean=0, std=0.01)
                if hasattr(m.bias, 'data'):
                    nn.init.constant_(m.bias, 0)

        return layers

def build_retinanet_shared_heads(args):
    return RetinaNet(backbone_models(args.basenet, args.model_dir, args.use_bias), args)