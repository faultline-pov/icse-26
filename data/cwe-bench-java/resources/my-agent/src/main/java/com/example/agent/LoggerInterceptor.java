package com.example.agent;

import net.bytebuddy.implementation.bind.annotation.SuperCall;
import net.bytebuddy.implementation.bind.annotation.Origin;
import net.bytebuddy.implementation.bind.annotation.RuntimeType;

import java.lang.reflect.Method;
import java.util.concurrent.Callable;

public class LoggerInterceptor {
    @RuntimeType
    public static Object intercept(@Origin Method method,
                                   @Origin Class<?> clazz,
                                   @SuperCall Callable<?> zuper) throws Exception {
        System.out.println("[INSTRUMENTATION] " + clazz.getName() + "#" + method.getName());
        return zuper.call(); // continue to original method
    }
}
