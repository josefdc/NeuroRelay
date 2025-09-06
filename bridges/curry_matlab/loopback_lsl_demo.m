% loopback_lsl_demo.m
FS=250; NCH=3; BLK_S=1.0; SAMPLES=round(FS*BLK_S);
addpath('path/a/liblsl-Matlab');
lib=lsl_loadlib();
info=lsl_streaminfo(lib,'DemoEEG','EEG',NCH,FS,'cf_float32','neurorelay-loopback');
outlet=lsl_outlet(info,0,360);
disp('Enviando bloques de ruido a LSL (Ctrl+C para parar)...')
while true
    x = randn(SAMPLES, NCH, 'single');
    outlet.push_chunk(x);
    pause(BLK_S);
end
