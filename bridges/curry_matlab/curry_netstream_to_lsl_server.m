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
addpath('path/a/liblsl-Matlab'); % <--- ajusta ruta a liblsl
lib  = lsl_loadlib();
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
    ud = s.UserData;
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
