<?php
// 假设的用户名和密码
$correctUsername = "user";
$correctPassword = "pass";

if ($_SERVER["REQUEST_METHOD"] == "POST") {
    $username = $_POST["username"];
    $password = $_POST["password"];

    // 验证用户名和密码
    if ($username == $correctUsername && $password == $correctPassword) {
        // 登录成功，跳转到另一个页面
        header("Location: welcome.php");
        exit();
    } else {
        // 登录失败，显示错误信息
        echo "Invalid username or password";
    }
}
?>