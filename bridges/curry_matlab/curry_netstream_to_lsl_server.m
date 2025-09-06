% bridges/curry_matlab/curry_netstream_to_lsl_server.m
% ====== Config ======
PORT        = 4000;
FS          = 1000;
NCH         = 32;
BLK_S       = 1.0;
STREAM_NAME = 'NeuroscanEEG';
LITTLE_ENDIAN = true;

SAMPLES   = round(FS * BLK_S);
BYTES_BLK = SAMPLES * NCH * 4;

% ====== LSL ======
thisdir = fileparts(mfilename('fullpath'));       % carpeta donde está este .m
addpath(fullfile(thisdir,'liblsl-Matlab'));       % liblsl-Matlab está al lado
lib = lsl_loadlib();
info = lsl_streaminfo(lib, STREAM_NAME, 'EEG', NCH, FS, 'cf_float32', 'neurorelay-bridge');
outlet = lsl_outlet(info, 0, 360);

% ====== TCP Server ======
srv = tcpserver("0.0.0.0", PORT, "Timeout", 5);
% Inicializa UserData para pasar estado al callback
ud.buf        = uint8([]);
ud.NCH        = NCH;
ud.SAMPLES    = SAMPLES;
ud.BYTES_BLK  = BYTES_BLK;
ud.LITTLE_ENDIAN = LITTLE_ENDIAN;
ud.outlet     = outlet;
srv.UserData  = ud;

disp("[TCP] Esperando conexión de CURRY (cliente)...");
srv.BytesAvailableFcn = @onBytes;

% --- Callback ---
function onBytes(s, ~)
    ud = s.UserDat% bridges/curry_matlab/curry_netstream_to_lsl_client.m
% ====== Config ======
CURRY_HOST = '192.168.50.10';  % IP del PC con CURRY (Server)
PORT       = 4000;             % Puerto NetStreaming (sin compresión)
FS         = 1000;             % Hz (muestreo real del stream)
NCH        = 32;               % # canales
BLK_S      = 1.0;              % segundos por bloque (1.0 si Blocks/s = 1)
STREAM_NAME = 'NeuroscanEEG';  % nombre LSL
LITTLE_ENDIAN = true;          % Windows/x86: true

SAMPLES   = round(FS * BLK_S);
BYTES_BLK = SAMPLES * NCH * 4; % float32

% ====== Conexión TCP (cliente) ======
t = tcpclient(CURRY_HOST, PORT, "Timeout", 5);
fprintf('[TCP] Conectado a %s:%d\n', CURRY_HOST, PORT);

% ====== LSL ======
addpath('path/a/liblsl-Matlab');   % <--- ajusta ruta a liblsl
lib  = lsl_loadlib();
info = lsl_streaminfo(lib, STREAM_NAME, 'EEG', NCH, FS, 'cf_float32', 'neurorelay-bridge');
outlet = lsl_outlet(info, 0, 360); % chunk=0 (variable), buffer=360 s

% ====== Bucle principal ======
buf = uint8([]);
while true
    n = t.NumBytesAvailable;
    if n > 0
        buf = [buf; read(t, n, 'uint8')]; %#ok<AGROW>
    else
        pause(0.003);
        continue;
    end
    while numel(buf) >= BYTES_BLK
        raw = buf(1:BYTES_BLK); 
        buf = buf(BYTES_BLK+1:end);

        x = typecast(raw, 'single');     % float32
        if ~LITTLE_ENDIAN, x = swapbytes(x); end
        x = reshape(x, [NCH, SAMPLES]).'; % [muestras x canales]
        outlet.push_chunk(x);
    end
end
a;
    n  = s.BytesAvailable;
    if n > 0
        ud.buf = [ud.buf; read(s, n, 'uint8')]; %#ok<AGROW>
    end
    while numel(ud.buf) >= ud.BYTES_BLK
        raw   = ud.buf(1:ud.BYTES_BLK);
        ud.buf = ud.buf(ud.BYTES_BLK+1:end);
        x = typecast(raw, 'single');
        if ~ud.LITTLE_ENDIAN, x = swapbytes(x); end
        x = reshape(x, [ud.NCH, ud.SAMPLES]).';
        ud.outlet.push_chunk(x);
    end
    s.UserData = ud;  % guardar estado actualizado
end
