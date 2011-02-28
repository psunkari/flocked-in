<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">

<head>
<title></title>
<script type="text/javascript">
    function validate()
    {
            mail= document.getElementById("c_email").value
            currentCity= document.getElementById("currentCity").value
            if (!(mail && currentCity) ){
                err = document.getElementById("error")
                err.style.color = "red"

                if (!currentCity){
                text = "Enter current-city"
                }
                if (!mail){
                    text = "Enter work emailId"
                }
                err.innerHTML = "Incomplete form!."+text
                return false
            }

        return true
    }
    function setDisabled(){

    txt = document.getElementById('language').value
    if (txt){
    document.getElementById("language_s").disabled = false
    document.getElementById("language_r").disabled = false
    document.getElementById("language_w").disabled = false


    }
    else {

    document.getElementById("language_w").disabled = true
    document.getElementById("language_s").disabled = true
    document.getElementById("language_r").disabled = true
    }

    }

</script>
    <meta http-equiv="Content-Type" content="text/html;charset=utf-8"/>
    <style type="text/css">
    table{

    border-spacing:10px;
    border-color:white;
    border-style:none;
    border-collapse:collapse;

    }
    th {
    text-align:left;
    background-color:#A7C942;
    margin:200px;
    border-spacing:100px;
    }
    td{
    text-align:left;
    padding-bottom:1px;
    }
    tr{
    margin:200px;
    }

    </style>
</head>
<body>

      <form action="/register/basic" method="post" enctype="multipart/form-data" onsubmit="return validate()">
        <table>
            <tr>
            <td id="error"></td>
            <td></td>
            <td></td>
            </tr>
            <tr>
                <th> Basic </th>
                <td></td>
                <td>
                    <label > ACL </label>
                    <select id="basic_acl" name="basic_acl">
                        <option> Friends </option>
                        <option selected="selected"> Company </option>
                        <option> Public </option>
                    </select>
                </td>

            </tr>
            <tr>
                <td> <label for="name"> Name </label> </td>
                <td> <input type ="text" id= "basic_name" name = "name"/> </td>
                <td></td>
            </tr>
            <tr>
                <td> <label for="jobTitle"> Designation </label> </td>
                <td> <input type ="text" id= "basic_jobTitle" name = "jobTitle"/> </td>
                <td></td>
            </tr>
            <tr>
                <td> <label for="location"> Location </label> </td>
                <td> <input type ="text" id= "basic_location" name = "location"/> </td>
                <td></td>
            </tr>
            <tr>
                <td> <label for="desc"> About </label> </td>
                <td> <textarea id= "basic_desc" name = "desc" rows="3"></textarea> </td>
                <td></td>
            </tr>

            <tr>
                <th> Avatar </th>
                <td></td>
                <td>
                    <label > ACL </label>
                    <select id="avatar_acl" name="avatar_acl">
                        <option> Friends </option>
                        <option selected="selected"> Company </option>
                        <option> Public </option>
                    </select>
                </td>
                <td></td>
            </tr>
            <tr>
                <td> <label for="dp"> Display Image </label> </td>
                <td> <input type ="file" id= "avatar_dp" name = "dp"/> </td>
                <td></td>
            </tr>
            <tr>
                <th> Expertise </th>
                <td></td>
                <td>
                    <label > ACL </label>
                    <select id="expertise_acl" name="expertise_acl">
                        <option> Friends </option>
                        <option selected="selected"> Company </option>
                        <option> Public </option>
                    </select>
                </td>
                <td></td>
            </tr>
            <tr>
                <td> <label for="expertise"> Expertise</label> </td>
                <td> <input type ="text" id= "expertise" name = "expertise"/> </td>
                <td></td>
            </tr>
            <tr>
                <th> Languages </th>
                <td></td>
                <td>
                    <label > ACL </label>
                    <select id="language_acl" name="language_acl">
                        <option> Friends </option>
                        <option selected="selected"> Company </option>
                        <option> Public </option>
                    </select>
                </td>
                <td></td>
            </tr>
            <tr>
                <td> <label for="languages"> Languages </label> </td>
                <td> <input type ="text" id= "language" name = "language" onblur="setDisabled()"/> </td>
                <td>
                    r:<input type="checkbox" id="language_r" name="language_r" disabled=true/>
                    w:<input type="checkbox" id="language_w" name="language_w" disabled=true/>
                    s:<input type="checkbox" id="language_s" name="language_s" disabled=true/>
                </td>
             </tr>
            <tr>
                <td colspan="3"> <hr/></td><td> </td><td> </td>
            </tr>


                <tr>
                <th> Work </th>
                <td></td>
                <td>
                    <label > ACL </label>
                    <select id="work_acl" name="work_acl">
                        <option> Friends </option>
                        <option selected="selected"> Company </option>
                        <option> Public </option>
                    </select>
                </td>
                <td></td>
            </tr>

            <tr>
                <td> <label for="employer">  </label> </td>
                <td> <input type ="text" id= "employer" name = "employer"/> </td>
                <td></td>
            </tr>
            <tr>
                <th> Contacts </th>
                <td></td>
                <td>
                    <label > ACL </label>
                    <select id="contact_acl" name="contacts_acl">
                        <option> Friends </option>
                        <option selected="selected"> Company </option>
                        <option> Public </option>
                    </select>
                </td>
                <td></td>
            </tr>
            <tr>
                <td> <label for="email"> Email </label> </td>
                <td> <input type ="text" id= "c_email" name = "c_email"/> </td>
                <td></td>
            </tr>
            <tr>
                <td> <label for="im"> IM </label> </td>
                <td> <input type ="text" id= "c_im" name = "c_im"/> </td>
                <td></td>
            </tr>
            <tr>
                <td> <label for="phone"> phone </label> </td>
                <td> <input type ="text" id= "c_phone" name = "c_phone"/> </td>
                <td></td>
            </tr>
            <tr>
                <td> <label for="im"> mobile </label> </td>
                <td> <input type ="text" id= "c_mobile" name = "c_mobile"/> </td>
                <td></td>
            </tr>
            <tr>
                <th> Interests </th>
                <td></td>
                <td>
                    <label > ACL </label>
                    <select id="interests_acl" name="interests_acl">
                        <option> Friends </option>
                        <option selected="selected"> Company </option>
                        <option> Public </option>
                    </select>
                </td>
                <td></td>
            </tr>
            <tr>
                <td> <label for="interests"> Interests </label> </td>
                <td> <input type ="text" id= "interests" name = "interests"/> </td>
                <td></td>
            </tr>
            <tr>
                <th> Personal </th>
                <td></td>
                <td>
                    <label > ACL </label>
                    <select id="personal_acl" name="personal_acl">
                        <option> Friends </option>
                        <option selected="selected"> Company </option>
                        <option> Public </option>
                    </select>
                </td>
                <td></td>
            </tr>
            <tr>
                <td> <label for="p_email"> Email </label> </td>
                <td> <input type ="text" id= "p_email" name = "p_email"/> </td>
                <td></td>
            </tr>
            <tr>
                <td> <label for="p_phone"> phone </label> </td>
                <td> <input type ="text" id= "p_phone" name = "p_phone"/> </td>
                <td></td>
            </tr>
            <tr>
                <td> <label for="p_mobile"> mobile </label> </td>
                <td> <input type ="text" id= "p_mobile" name = "p_mobile"/> </td>
                <td></td>
            </tr>
            <tr>
                <td> <label for= "hometown"> Hometown </label> </td>
                <td> <input type ="text" id= "hometown" name = "hometown"/> </td>
                <td></td>
            </tr>
            <tr>
                <td> <label for= "currentCity"> currentCity </label> </td>
                <td> <input type ="text" id= "currentCity" name = "currentCity"/> </td>
                <td></td>
            </tr>

            <tr>
                <td></td>
                <td> <input type="submit" name="userInfo_submit" value="Submit"> Submit </input> </td>
                <td></td>
            </tr>

            <tr>
                <td>
                    <input type="hidden" value = ${emailId[0]} name="emailId" />
                </td>
                <td></td>
                <td></td>
            </tr>
        </table>

    </form>
</body>
</html>
