$(document).ready(function () {
    const queryString = window.location.search;
    const urlParams = new URLSearchParams(queryString);
    const patienid = urlParams.get('id')

// Filter objects by name using jQuery
    function filterBypatid2(array, id) {
        return $.grep(array, function(obj) {
            return obj.pat_id === id;
        });
    };

    var table
 
    function addAppointment(data) {
        var table
       console.log(data);
        var settings = {
            "async": true,
            "crossDomain": true,
            "url": "appointmentapi",
            "method": "POST",
            "headers": {
                "content-type": "application/json",
                "cache-control": "no-cache",
                "postman-token": "2612534b-9ccd-ab7e-1f73-659029967199"
            },
            "processData": false,
            "data": JSON.stringify(data)
        }
        $.ajax(settings).done(function (response) {
         $.notify("Appointment Added Successfully", {"status":"success"});
            $('.modal.in').modal('hide')
            //table.destroy();
            $('#datatable5 tbody').empty(); // empty in case the columns change   
             
            //send mail 
            let f = new FormData();
            f.append("id",data.pat_id)
            f.append("doc_id",data.doc_id)
            f.append("appointment_date",data.appointment_date)
            console.log('email')
            fetch("/send-mail",{
            "method": "POST",
            "body":f,       
            }).then(response => response.text()).then(data => {               
            });
            getAppointment()
        });

    }

    function deleteAppointment(id) {
        var settings = {
            "async": true,
            "crossDomain": true,
            "url": "appointmentapi/" + id,
            "method": "DELETE",
            "headers": {
                "cache-control": "no-cache",
                "postman-token": "28ea8360-5af0-1d11-e595-485a109760f2"
            }
        }

swal({
    title: "Are you sure?",
    text: "You will not be able to recover this data",
    type: "warning",
    showCancelButton: true,
    confirmButtonColor: "#DD6B55",
    confirmButtonText: "Yes, delete it!",
    closeOnConfirm: false
}, function() {
 $.ajax(settings).done(function (response) {
   swal("Deleted!", "Appointment has been deleted.", "success");
            table.destroy();
            $('#datatable5 tbody').empty(); // empty in case the columns change
            getAppointment()
        });


});

    }

    function getAppointment() {
        const queryString = window.location.search;
        const urlParams = new URLSearchParams(queryString);
        var patid = urlParams.get('id');

        var settings = {
            "async": true,
            "crossDomain": true,
            "url": "appointmentapi",
            "method": "GET",
            "headers": {
                "cache-control": "no-cache"
            }
        }

        $.ajax(settings).done(function (response) {

        //filter response' by pat_id
         response =  filterByPatid2(response,patid);
         console.log(response)
        for(i=0;i<response.length;i++){
        response[i].pat_fullname=response[i].pat_first_name+" "+response[i].pat_last_name
        response[i].doc_fullname=response[i].doc_first_name+" "+response[i].doc_last_name
        }



            table = $('#datatable5').DataTable({
                "bDestroy": true,
                'paging': true, // Table pagination
                'ordering': true, // Column ordering
                'info': true, // Bottom left status text
                aaData: response,
                   "aaSorting": [],
                aoColumns: [
                    {
                        mData: 'doc_fullname'
                    },
                    {
                        mData: 'pat_fullname'
                    },
                    {
                        mData: 'appointment_date'
                    },
                    {
                        mRender: function (o) {
                            return '<button class="btn-xs btn btn-danger delete-btn" type="button">Delete</button>';
                        }
                    }
        ]
            });
            $('#datatable5 tbody').on('click', '.delete-btn', function () {
                var data = table.row($(this).parents('tr')).data();
                deleteAppointment(data.app_id)
            });


        });


    }

    $("#addpatient").click(function () {

        $('#myModal').modal().one('shown.bs.modal', function (e) {

        $("#doctor_select").html(doctorSelect)
        $("#patient_select").html(patientSelect)

        console.log("open modal",patienid)
        $("#patient_select").val(patienid); 
     
        $(".form_datetime").datetimepicker({
            format: 'yyyy-mm-dd hh:ii:00',
            startDate:new Date(),
            initialDate: new Date()
        });
            $("#savethepatient").off("click").on("click", function(e) {
            var instance = $('#detailform').parsley();
            instance.validate()
             if(instance.isValid()){
                jsondata = $('#detailform').serializeJSON();
                let pat_id = jsondata.pat_id;
                addAppointment(jsondata);
                //send mail to patient
                  
                }
              
            })

        })



    })


var doctorSelect=""
 function getDoctor() {

        var settings = {
            "async": true,
            "crossDomain": true,
            "url": "doctorapi",
            "method": "GET",
            "headers": {
                "cache-control": "no-cache"
            }
        }

        $.ajax(settings).done(function (response) {

        for(i=0;i<response.length;i++){

        response[i].doc_fullname=response[i].doc_first_name+" "+response[i].doc_last_name
        doctorSelect +="<option value="+response[i].doc_id+">"+response[i].doc_fullname+"</option>"
        }


        })
        }
var patientSelect=""

  function getPatient(patienid) {

        var settings = {
            "async": true,
            "crossDomain": true,
            "url": "patientapi?id="+ patienid,
            "method": "GET",
            "headers": {
                "cache-control": "no-cache"
            }
        }

        $.ajax(settings).done(function (response) {
         for(i=0;i<response.length;i++){
          response[i].pat_fullname=response[i].pat_first_name+" "+response[i].pat_last_name
        patientSelect +="<option value="+response[i].pat_id+">"+response[i].pat_fullname+"</option>"
        }

                })
        }

getDoctor()
getPatient(patienid)
getAppointment()


// Function to filter objects by name
async function filterByPatid(array, patid) {
    return array.filter(function(obj) {
        return obj.pat_id === patid;
    });
}


})