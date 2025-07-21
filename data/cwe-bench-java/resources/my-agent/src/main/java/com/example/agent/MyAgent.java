package com.example.agent;

import net.bytebuddy.agent.builder.AgentBuilder;
import net.bytebuddy.matcher.ElementMatchers;
import net.bytebuddy.implementation.MethodDelegation;
import net.bytebuddy.description.type.TypeDescription;
import net.bytebuddy.dynamic.DynamicType;
import net.bytebuddy.utility.JavaModule;

import java.lang.instrument.Instrumentation;
import java.security.ProtectionDomain;
import java.util.*;

public class MyAgent {
    public static void premain(String agentArgs, Instrumentation inst) {
        String methodsEnv = System.getenv("METHODS_TO_INSTRUMENT");
        if (methodsEnv == null || methodsEnv.isEmpty()) {
            // System.out.println("[AGENT] METHODS_TO_INSTRUMENT is not set or empty. Skipping instrumentation.");
            return;
        }

        // Map from simple class name -> Set of method names
        Map<String, Set<String>> methodMap = new HashMap<>();

        String[] lines = methodsEnv.split("\\\\n"); // split on literal '\n'
        for (String line : lines) {
            String[] parts = line.split(",");
            if (parts.length == 2) {
                String fullClassName = parts[0].trim();
                String methodName = parts[1].trim();
                if (!fullClassName.isEmpty() && !methodName.isEmpty()) {
                    String simpleName = fullClassName.substring(fullClassName.lastIndexOf('.') + 1);
                    methodMap.computeIfAbsent(simpleName, k -> new HashSet<>()).add(methodName);
                }
            }
        }

        if (methodMap.isEmpty()) {
            // System.out.println("[AGENT] No methods to instrument after parsing.");
            return;
        }

        // System.out.println("[AGENT] Starting instrumentation for: " + methodMap);

        new AgentBuilder.Default()
            .type((typeDescription, classLoader, module, classBeingRedefined, protectionDomain) -> {
                String simpleName = typeDescription.getSimpleName();
                return methodMap.containsKey(simpleName);
            })
            .transform((builder, typeDescription, classLoader, module, pd) -> {
                String simpleName = typeDescription.getSimpleName();
                Set<String> methodNames = methodMap.getOrDefault(simpleName, Collections.emptySet());
                if (methodNames.isEmpty()) {
                    return builder;
                }
                return builder.method(ElementMatchers.namedOneOf(methodNames.toArray(new String[0])))
                              .intercept(MethodDelegation.to(LoggerInterceptor.class));
            })
            .installOn(inst);
    }
}
