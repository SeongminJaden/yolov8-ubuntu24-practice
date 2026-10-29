"""Create a dimensioned SVG AprilTag, preserving the 1-cell white quiet zone."""
import argparse
from pathlib import Path
import cv2

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--id',type=int,required=True);p.add_argument('--black-size-mm',type=float,default=16)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if not 0<=a.id<587:p.error('tag36h11 ID must be 0..586')
    if not 0<a.black_size_mm<=16.97:p.error('Tag plus quiet zone must fit the diameter 30mm top')
    if a.output.exists():p.error('Output exists')
    bits=cv2.aruco.generateImageMarker(cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11),a.id,8)
    total=a.black_size_mm*1.25
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{total}mm" height="{total}mm" viewBox="0 0 10 10" shape-rendering="crispEdges">',f'<title>tag36h11 ID {a.id}; black edge {a.black_size_mm} mm</title>','<rect width="10" height="10" fill="white"/>']
    for y,row in enumerate(bits):
        for x,pixel in enumerate(row):
            if pixel==0:svg.append(f'<rect x="{x+1}" y="{y+1}" width="1" height="1" fill="black"/>')
    svg.append('</svg>');a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text('\n'.join(svg)+'\n')

if __name__=='__main__':main()
