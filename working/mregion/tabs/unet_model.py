# mregion/tabs/unet_model.py
from __future__ import annotations

__all__ = ["UNet", "TORCH_OK"]

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_OK = True
except Exception as e:  # PyTorch unavailable
    TORCH_OK = False
    torch = None  # type: ignore[assignment]
    nn = None     # type: ignore[assignment]
    F = None      # type: ignore[assignment]
    TORCH_IMPORT_ERROR = e  # type: ignore[assignment]

if TORCH_OK:
    class DoubleConv(nn.Module):
        def __init__(self, in_ch: int, out_ch: int):
            super().__init__()
            self.net = nn.Sequential(
                nn.Conv2d(in_ch, out_ch, 3, padding=1, bias=False),
                nn.BatchNorm2d(out_ch),
                nn.ReLU(inplace=True),
                nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
                nn.BatchNorm2d(out_ch),
                nn.ReLU(inplace=True),
            )
        def forward(self, x):
            return self.net(x)

    class Down(nn.Module):
        def __init__(self, in_ch: int, out_ch: int):
            super().__init__()
            self.pool = nn.MaxPool2d(2)
            self.conv = DoubleConv(in_ch, out_ch)
        def forward(self, x):
            return self.conv(self.pool(x))

    class Up(nn.Module):
        def __init__(self, in_ch: int, out_ch: int):
            super().__init__()
            self.up = nn.ConvTranspose2d(in_ch, in_ch // 2, 2, 2)
            self.conv = DoubleConv(in_ch, out_ch)
        def forward(self, x1, x2):
            x1 = self.up(x1)
            dy = x2.size(2) - x1.size(2)
            dx = x2.size(3) - x1.size(3)
            if dy or dx:
                x1 = F.pad(x1, (0, dx, 0, dy))
            x = torch.cat([x2, x1], dim=1)
            return self.conv(x)

    class UNet(nn.Module):
        def __init__(self, in_ch: int = 3, n_classes: int = 2):
            super().__init__()
            self.inc = DoubleConv(in_ch, 64)
            self.down1 = Down(64, 128)
            self.down2 = Down(128, 256)
            self.down3 = Down(256, 512)
            self.down4 = Down(512, 512)
            self.up1 = Up(512, 256)
            self.up2 = Up(256, 128)
            self.up3 = Up(128, 64)
            self.up4 = Up(64, 64)
            self.outc = nn.Conv2d(64, n_classes, 1)
        def forward(self, x):
            x1 = self.inc(x)
            x2 = self.down1(x1)
            x3 = self.down2(x2)
            x4 = self.down3(x3)
            x5 = self.down4(x4)
            x = self.up1(x5, x4)
            x = self.up2(x, x3)
            x = self.up3(x, x2)
            x = self.up4(x, x1)
            return self.outc(x)
else:
    UNet = None  # type: ignore[assignment]
