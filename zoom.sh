#!/bin/sh

if (( $# != 1 )); then
    >&2 echo "Illegal number of parameters"
fi

export ZOOM_MEETING_ID=$1
export QT_QPA_PLATFORM=xcb
export QSG_INFO=1
export LD_LIBRARY_PATH=/opt/zoom
export BREAKPAD_CLIENT_FD=3

/opt/zoom/zoom "--url=zoommtg://zoom.us/join?action=join&confno=${ZOOM_MEETING_ID}" &

sleep 15

for i in `pacmd list-sources | grep index | cut -d: -f2`; do
    echo "Setting volume of source $i"
    pacmd set-source-volume $i 72000
done

for i in `pacmd list-sinks | grep index | cut -d: -f2`; do
    echo "Setting volume of sink $i"
    pacmd set-sink-volume $i 72000
done

for i in `pacmd list-source-outputs | grep index | cut -d: -f2`; do
    echo "Setting volume of source output $i"
    pacmd set-source-output-volume $i 72000
done

for i in `pacmd list-sink-inputs | grep index | cut -d: -f2`; do
    echo "Setting volume of sink input $i"
    pacmd set-sink-input-volume $i 72000
done
