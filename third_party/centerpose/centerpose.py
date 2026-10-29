# SPDX-FileCopyrightText: Copyright (c) 2023 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
# DLA34 class extracted unchanged; optional FAN imports removed.
from torch import nn
import numpy as np
from .model_utils import ConvGRU,DLAUp,IDAUp,fill_fc_weights,get_dla_base,group_norm

class CenterPose_DLA34(nn.Module):
    """ This method mainly focuses on the Category-Level 6-DoF pose estimation from a single RGB image. """

    def __init__(self, model_config):
        """ Initializes the CenterPose model with DLA34 backbone.
        """
        super(CenterPose_DLA34, self).__init__()

        down_ratio = model_config.down_ratio
        final_kernel = model_config.final_kernel
        last_level = model_config.last_level
        head_conv = model_config.head_conv
        out_channel = model_config.out_channel
        use_convGRU = model_config.use_convGRU

        assert down_ratio in [2, 4, 8, 16], "only support downsample ratio in [2, 4, 8, 16]"
        self.heads = {'hm': 1, 'wh': 2, 'hps': 16, 'reg': 2, 'hm_hp': 8, 'hp_offset': 2, 'scale': 3}

        self.first_level = int(np.log2(down_ratio))
        self.last_level = last_level
        self.base = get_dla_base(pretrained=model_config.use_pretrained)
        channels = self.base.channels
        scales = [2 ** i for i in range(len(channels[self.first_level:]))]
        self.dla_up = DLAUp(self.first_level, channels[self.first_level:], scales)

        self.use_convGRU = use_convGRU
        if self.use_convGRU is True:
            self.convGRU = ConvGRU(input_channels=channels[self.first_level],
                                   hidden_channels=[64, ],
                                   kernel_size=3, step=3,
                                   effective_step=[0, 1, 2])

        if out_channel == 0:
            out_channel = channels[self.first_level]

        self.ida_up = IDAUp(out_channel, channels[self.first_level:self.last_level],
                            [2 ** i for i in range(self.last_level - self.first_level)])

        for head in self.heads:
            classes = self.heads[head]
            if head_conv > 0:

                modules = []
                modules.append(nn.Conv2d(channels[self.first_level], head_conv,
                                         kernel_size=3, padding=1, bias=True))

                if self.use_convGRU is True:
                    modules.append(group_norm(head_conv))

                modules.append(nn.ReLU(inplace=True))
                modules.append(nn.Conv2d(head_conv, classes,
                                         kernel_size=final_kernel, stride=1,
                                         padding=final_kernel // 2, bias=True))

                fc = nn.Sequential(*modules)

                if 'hm' in head:
                    fc[-1].bias.data.fill_(-2.19)
                else:
                    fill_fc_weights(fc)
            else:
                fc = nn.Conv2d(channels[self.first_level], classes,
                               kernel_size=final_kernel, stride=1,
                               padding=final_kernel // 2, bias=True)
                if 'hm' in head:
                    fc.bias.data.fill_(-2.19)
                else:
                    fill_fc_weights(fc)
            self.__setattr__(head, fc)

    def forward(self, x):
        """ Forward function of CenterPose Model

        Args:
            samples (torch.Tensor): batched images, of shape [batch_size x 3 x H x W]

        Returns:
            z (Dict): the heatmaps indicate the keypoints location.

        """
        x = self.base(x)
        x = self.dla_up(x)

        y = []
        for i in range(self.last_level - self.first_level):
            y.append(x[i].clone())
        self.ida_up(y, 0, len(y))

        z = {}

        # Feature association
        if self.use_convGRU is True:
            gru_outputs, _ = self.convGRU(y[-1])

            for head in self.heads:
                if head in ['hm', 'wh', 'reg']:
                    z[head] = self.__getattr__(head)(gru_outputs[0])
                if head in ['hm_hp', 'hp_offset', 'hps']:
                    z[head] = self.__getattr__(head)(gru_outputs[1])
                if head == 'scale':
                    z[head] = self.__getattr__(head)(gru_outputs[2])

        else:
            for head in self.heads:
                z[head] = self.__getattr__(head)(y[-1])

        return [z]
