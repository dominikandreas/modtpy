const handleError = error => {
  if (error !== undefined && error.message !== undefined) {
    $("#printer-status").text(error.message);
  }
};

const stateTypes = {
  STATE_LOADFIL_HEATING: "Loading filament: heating",
  STATE_LOADFIL_EXTRUDING: "Loading filament: extruding",
  STATE_REMFIL_HEATING: "Unloading filament: heating",
  STATE_REMFIL_RETRACTING: "Unloading filament: retracting",
  STATE_IDLE: "Idle",
  STATE_FILE_RX: "Receiving GCODE",
  STATE_JOB_QUEUED: "Job queued",
  STATE_JOB_PREP: "Preparing Job",
  STATE_HOMING_XY: "Calibrating X/Y axis",
  STATE_HOMING_HEATING: "Heating up",
  STATE_HOMING_Z_ROUGH: "Calibrating Z axis rough",
  STATE_HOMING_Z_FINE: "Calibrating Z axis fine",
  STATE_BUILDING: "Printing",
  STATE_EXEC_PAUSE_CMD: "Pausing",
  STATE_PAUSED: "Paused",
  STATE_UNPAUSED: "Resuming",
  STATE_MECH_READY: "Print finished"
};

const getStatus = () => {
  $.getJSON({
    url: "/printer/status"
  })
    .done(payload => {
      setMode(payload.mode);
      setStatus(payload.status);
      setLogs(payload.logs);
    })
    .fail(payload => {
      handleError(payload.responseJSON);
    });
};


document.logged_messages = {};


const setLogs = logs => {
  let logs_div = $(".logs")[0];
  logs.forEach(log => {
    if (document.logged_messages[log.id] === undefined){
      let el = document.createElement("p");
      document.logged_messages[log.id] = 1
      el.innerHTML = document.ansispan(log.message);
      logs_div.appendChild(el);
    }
  })
}

const setStatus = status => {
  if (!status || !status.status) {
    $(".modtpy-status").text("");
    $(".modtpy-status-temp").text("");
    $(".modtpy-status-temp-0").show();
    $(".modtpy-status-temp-1").hide();
    $(".modtpy-status-temp-2").hide();
    $(".modtpy-status-temp-3").hide();
    $(".modtpy-status-temp-4").hide();
    return;
  }
  $(".modtpy-status").text(stateTypes[status.status.state]);
  setTemperature(
    status.status.extruder_temperature,
    status.status.extruder_target_temperature
  );
  if (status.job !== undefined) {
    setProgress(status.job.progress);
  }
};

const setTemperature = (current, max) => {
  $(".modtpy-status-temp").text(current + "° / " + max + "°");
  $(".modtpy-status-temp-0").hide();
  $(".modtpy-status-temp-1").hide();
  $(".modtpy-status-temp-2").hide();
  $(".modtpy-status-temp-3").hide();
  $(".modtpy-status-temp-4").hide();
  const ratio = Math.max(Math.min(current / max, 1), 0);
  const scale = Math.round(ratio * 4);
  $(".modtpy-status-temp-" + scale).show();
};

const setProgress = progress => {
  try{
     parseInt(progress);
     let el = $(".modtpy-status-progress-display");
     el.text(progress + "%");
     el.show()
     $(".modtpy-status-progress").show();
  } catch (e) {
    $(".modtpy-status-progress").hide();
    $(".modtpy-status-progress-display").hide()
  }
}
const setMode = mode => {
  mode = mode.toUpperCase();
  if (mode === "DISCONNECTED" || mode === "DFU") {
    $(".modtpy-mode-connected").hide();
    $(".modtpy-mode-disconnected").show();
  } else if (mode === "OPERATE") {
    $(".modtpy-mode-connected").show();
    $(".modtpy-mode-disconnected").hide();
  }
  $(".modtpy-mode").text(mode.toLowerCase());
};

const pollStatus = () => {
  getStatus();
  setInterval(getStatus, 2000);
};


const loadFilament = () => {
  $.getJSON({
    url: "/printer/load-filament"
  }).done(payload => {
    setMode(payload.mode);
    setStatus(payload.status);
  }).fail(payload => {
    handleError(payload.responseJSON);
  });
}

const unloadFilament = () => {
  $.getJSON({
    url: "/printer/unload-filament"
  }).done(payload => {
    setMode(payload.mode);
    setStatus(payload.status);
  }).fail(payload => {
    handleError(payload.responseJSON);
  });
}

const uploadGcode = () => {
  let choose_btn = $("#gcode_btn_file_choose")[0];

  choose_btn.onchange = (event) =>{
    let file = event.target.files[0]
    let fd = new FormData();
    fd.append('file', file);
    $.ajax({
        url: 'printer/upload-gcode',
        type: 'post',
        data: fd,
        contentType: false,
        processData: false,
        success: function(response){
            if(response != 0){
               alert('file uploaded');
            }
            else{
                alert('file not uploaded');
            }
        },
    });
  }

  choose_btn.click();
}

$(() => {
  pollStatus();
  $("#btn-load")[0].onclick = loadFilament;
  $("#btn-unload")[0].onclick = unloadFilament;
  $("#btn-gcode")[0].onclick = uploadGcode;
});
