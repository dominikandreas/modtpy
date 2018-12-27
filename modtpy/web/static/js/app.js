const handleError = error => {
  $("#printer-status").text(error.message);
};

const getStatus = () => {
  $.getJSON({
    url: "/printer/status"
  })
    .done(payload => {
      setStatus(payload);
    })
    .fail(payload => {
      handleError(payload.responseJSON);
    });
};

const setStatus = payload => {
  $("#printer-mode").text(payload.mode);
  if (payload.status && payload.status.status) {
    $("#printer-status").text(payload.status.status.state);
  } else {
    $("#printer-status").text("");
  }
};

const pollStatus = () => {
  getStatus();
  setInterval(() => {
    getStatus();
  }, 3000);
};

$(() => {
  pollStatus();
});
