var testSexagesimal = /^[+-]?\d+:\d+:\d+(\.\d+)?$/;
var targetData = [];

function generateChart(t) {
  var url = generateURL + '?survey='+t.survey+'&size='+t.size+'&outepoch='+t.outepoch+'&ra='+t.ra+'&dec='+t.dec+'&rapm='+t.rapm+'&decpm='+t.decpm+'&epoch='+t.epoch

  var chartWidth = t.annotate ? 522 : 512;
  var chartHeight = t.annotate ? 612 : 512;
  var chartImageX = t.annotate ? 5 : 0;
  var chartImageY = t.annotate ? 20 : 0;

  var chartCanvas = $('<canvas/>').prop({width: chartWidth, height: chartHeight});
  var chartContext = chartCanvas[0].getContext('2d');
  targetData.push([t, chartCanvas[0]]);

  chartContext.fillStyle = '#fff';
  chartContext.fillRect(0, 0, chartWidth, chartHeight);

  chartContext.strokeStyle = '#000';
  chartContext.lineWidth = 2;
  chartContext.strokeRect(chartImageX+1, chartImageY+1, 510, 510);
  chartContext.font = '28px serif';
  chartContext.textAlign = 'center'
  chartContext.fillStyle = '#000';
  chartContext.fillText('Generating...', chartWidth / 2, chartImageY + 256);

  if (t.annotate) {
    chartContext.font = '18px serif';
    chartContext.fillText(t.name, chartWidth / 2, 15);

    chartContext.fillText('J2000 coordinates at J' + t.outepoch, chartWidth / 2, chartHeight - 60);
    chartContext.fillText('RA: ' + t.ra, chartWidth / 4, chartHeight - 35);
    chartContext.fillText('Dec: ' + t.dec, 3 * chartWidth / 4, chartHeight - 35);

    if (t.comment)
      chartContext.fillText(t.comment, chartWidth / 2, chartHeight - 5);
  }

  var thumbContainer = $('<div>', {id: '', 'class': 'col-md-2 col-sm-4 col-xs-6 m-b'});
  var thumbBorder = $('<div>', {'class': 'btn list-group list-group-item thumb-panel'});
  thumbBorder.popover({
      trigger : 'hover',
      placement: 'top',
      html: true,
      container: 'body',
      content: chartCanvas,
  });
  thumbContainer.append(thumbBorder);

  var thumbLabel = $('<div>', {'class': 'thumb-label'}).text(t.name);
  thumbBorder.append(thumbLabel);

  var thumbImage = $('<img>', {'src': loadingURL, 'class': 'thumb-loading', 'width': 32, 'height': 32});
  thumbBorder.append(thumbImage);

  $('#thumbrow').append(thumbContainer);

  var img = new Image();
  img.addEventListener('load', function() {
    chartContext.drawImage(img, chartImageX, chartImageY);

    // Direction indicator
    chartContext.lineWidth = 2;
    chartContext.strokeStyle = '#0000FF';
    chartContext.beginPath();
    chartContext.moveTo(chartImageX + 502, chartImageY + 462);
    chartContext.lineTo(chartImageX + 502, chartImageY + 502);
    chartContext.lineTo(chartImageX + 462, chartImageY + 502);
    chartContext.stroke();

    chartContext.fillStyle = '#0000FF';
    chartContext.font = '12px sans-serif';
    chartContext.fillText('E', chartImageX + 455, chartImageY + 506);
    chartContext.fillText('N', chartImageX + 502, chartImageY + 457);

    // Scale indicator
    chartContext.beginPath();
    chartContext.moveTo(chartImageX + 10, chartImageY + 502);
    chartContext.lineTo(chartImageX + 10 + 512 / t.size, chartImageY + 502);
    chartContext.stroke();
    chartContext.fillText('1\'', chartImageX + 10 + 256 / t.size, chartImageY + 497);

    thumbImage.removeClass('thumb-loading');
    thumbImage.prop('src', url);
    thumbImage.width(128);
    thumbImage.height(128);
  }, false);

  img.addEventListener('error', function() {
    chartContext.fillStyle = '#fff';
    chartContext.fillRect(chartImageX+2, chartImageY+2, 508, 508);
    chartContext.font = '28px serif';
    chartContext.textAlign = 'center'
    chartContext.fillStyle = '#000';
    chartContext.fillText('Source Image Unavailable', chartWidth / 2, chartImageY + 256);
    thumbImage.prop('src', failedURL);
  }, false);

  img.src = url;
}

function setup() {
  // Calculate the current fractional year
  var now = new Date();
  $('#outepoch').val((now.getUTCFullYear() + now.getUTCMonth() / 12.0).toFixed(2));

  $('#download').hide();
  $('#download').click(function() {
    if (targetData.length == 0)
      return;

    var zip = new JSZip();
    for (var i in targetData) {
      var data = new Image();
      data.src = targetData[i][1].toDataURL();
      zip.file(targetData[i][0].name + '.png', data.src.substr(data.src.indexOf(',')+1), {base64: true});
    }

    zip.generateAsync({type:'blob'}).then(function (blob) {
      saveAs(blob, 'charts.zip');
    });
  });

  $('#generate').click(function() {
    var outepoch = $("input[name='outepoch']").val();
    var size = $("input[name='size']").val();
    var survey = $("select[name='survey']").val();
    var type = $("input[name='type']:checked").val();
    var coords = $("textarea[name='coords']").val().split('\n');

    if (parseFloat(size) != size) {
      $('#error').html('Unable to parse "' + size + '" as a number');
      return;
    }

    if (size <= 1 || size > 100) {
      $('#error').html('Field size must be between 1 and 100 arcmin');
      return;
    }

    if (parseFloat(outepoch) != outepoch) {
      $('#error').html('Unable to parse "' + outepoch + '" as a number');
      return;
    }

    if (outepoch <= 1900 || outepoch > 2100) {
      $('#error').html('Observing epoch must be between 1900 and 2100');
      return;
    }

    $('#error').html('');
    $('#thumbrow').empty();
    $('#chartrow').empty();
    targetData = [];

    var targets = [];
    for (var i in coords)
    {
      var parts = coords[i].split(/\s+/);
      var line = Number(i) + 1;

      // Skip blank lines
      if (parts.length == 1 && parts[0] == '')
        continue;

      var name = parts[0];
      var ra = parts[1];
      var dec = parts[2];
      var rapm = parts[3];
      var decpm = parts[4];
      var epoch = parts[5];

      if (ra === undefined || !testSexagesimal.test(ra)) {
        $('#error').html('Line ' + line + ': Unable to parse "' + ra + '" as HH:MM:SS');
        return;
      }

      if (dec === undefined || !testSexagesimal.test(dec)) {
        $('#error').html('Line ' + line + ': Unable to parse "' + dec + '" as DD:MM:SS');
        return;
      }

      if (rapm === undefined || parseFloat(rapm) != rapm) {
        $('#error').html('Line ' + line + ': Unable to parse "' + rapm + '" as number');
        return;
      }

      if (decpm === undefined || parseFloat(decpm) != decpm) {
        $('#error').html('Line ' + line + ': Unable to parse "' + decpm + '" as number');
        return;
      }

      if (epoch === undefined || parseFloat(epoch) != epoch) {
        $('#error').html('Line ' + line + ': Unable to parse "' + epoch + '" as number');
        return;
      }

      // Enumerate through line to find start of comment (if it exists)
      // Want to make sure we take all character from the start of the comment
      var comment = undefined;
      if (parts.length > 6) {
        var start = 0;
        for (var j = 0; j < 7; j++)
          start = coords[i].indexOf(parts[j], start);
        comment = coords[i].substring(start);
      }

      targets.push({
        'name': name,
        'ra': ra,
        'dec': dec,
        'rapm': rapm,
        'decpm': decpm,
        'epoch': epoch,
        'comment': comment,
        'survey': survey,
        'size': size,
        'annotate': type == 'annotated',
        'outepoch': outepoch,
      });
    }

    if (targets.length == 0)
      return;

    $('#generate').removeClass('btn-primary').addClass('btn-default').text('Regenerate');
    $('#download').show();
    for (i in targets)
      generateChart(targets[i]);
  });
}
